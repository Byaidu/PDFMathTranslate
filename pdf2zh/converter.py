import io
import logging
import re
from typing import (
    BinaryIO,
    Dict,
    Generic,
    List,
    Optional,
    Sequence,
    TextIO,
    Tuple,
    TypeVar,
    Union,
    cast,
)
import concurrent.futures
import numpy as np
import html
import requests
import unicodedata
import tqdm.auto
from tenacity import retry
from pdf2zh import cache
def remove_control_characters(s):
    return "".join(ch for ch in s if unicodedata.category(ch)[0]!="C")

from pdf2zh import utils
from pdf2zh.image import ImageWriter
from pdf2zh.layout import (
    LAParams,
    LTAnno,
    LTChar,
    LTComponent,
    LTContainer,
    LTCurve,
    LTFigure,
    LTImage,
    LTItem,
    LTLayoutContainer,
    LTLine,
    LTPage,
    LTRect,
    LTText,
    LTTextBox,
    LTTextBoxVertical,
    LTTextGroup,
    LTTextLine,
    TextGroupElement,
)
from pdf2zh.pdfcolor import PDFColorSpace
from pdf2zh.pdfdevice import PDFTextDevice
from pdf2zh.pdfexceptions import PDFValueError
from pdf2zh.pdffont import PDFFont, PDFUnicodeNotDefined, PDFCIDFont
from pdf2zh.pdfinterp import PDFGraphicState, PDFResourceManager
from pdf2zh.pdfpage import PDFPage
from pdf2zh.pdftypes import PDFStream
from pdf2zh.utils import (
    AnyIO,
    Matrix,
    PathSegment,
    Point,
    Rect,
    apply_matrix_pt,
    bbox2str,
    enc,
    make_compat_str,
    mult_matrix,
    matrix_scale,
)

log = logging.getLogger(__name__)

class Translator:
    def __init__(self):
        self.session = requests.Session()
        self.base_link = "http://translate.google.com/m"
        self.headers = {'User-Agent':'Mozilla/4.0 (compatible;MSIE 6.0;Windows NT 5.1;SV1;.NET CLR 1.1.4322;.NET CLR 2.0.50727;.NET CLR 3.0.04506.30)'}
    
    def translate(self, to_translate, to_language="auto", from_language="auto"):
        response = self.session.get(self.base_link, params={'tl':to_language,'sl':from_language,'q':to_translate}, headers=self.headers)
        re_result = re.findall(r'(?s)class="(?:t0|result-container)">(.*?)<', response.text)
        if len(re_result) == 0:
            result = ""
        else:
            result = html.unescape(re_result[0])
        return result

class PDFLayoutAnalyzer(PDFTextDevice):
    cur_item: LTLayoutContainer
    ctm: Matrix

    def __init__(
        self,
        rsrcmgr: PDFResourceManager,
        pageno: int = 1,
        laparams: Optional[LAParams] = None,
    ) -> None:
        PDFTextDevice.__init__(self, rsrcmgr)
        self.pageno = pageno
        self.laparams = laparams
        self._stack: List[LTLayoutContainer] = []

    def begin_page(self, page: PDFPage, ctm: Matrix) -> None:
        # (x0, y0, x1, y1) = page.mediabox
        (x0, y0, x1, y1) = page.cropbox
        (x0, y0) = apply_matrix_pt(ctm, (x0, y0))
        (x1, y1) = apply_matrix_pt(ctm, (x1, y1))
        mediabox = (0, 0, abs(x0 - x1), abs(y0 - y1))
        self.cur_item = LTPage(page.pageno, mediabox)

    def end_page(self, page: PDFPage):
        assert not self._stack, str(len(self._stack))
        assert isinstance(self.cur_item, LTPage), str(type(self.cur_item))
        # 取消默认排版分析
        # if self.laparams is not None:
        #     self.cur_item.analyze(self.laparams)
        self.pageno += 1
        return self.receive_layout(self.cur_item)

    def begin_figure(self, name: str, bbox: Rect, matrix: Matrix) -> None:
        self._stack.append(self.cur_item)
        self.cur_item = LTFigure(name, bbox, mult_matrix(matrix, self.ctm))
        self.cur_item.pageid = self._stack[-1].pageid

    def end_figure(self, _: str) -> None:
        fig = self.cur_item
        assert isinstance(self.cur_item, LTFigure), str(type(self.cur_item))
        self.cur_item = self._stack.pop()
        self.cur_item.add(fig)
        return self.receive_layout(fig)

    def render_image(self, name: str, stream: PDFStream) -> None:
        assert isinstance(self.cur_item, LTFigure), str(type(self.cur_item))
        item = LTImage(
            name,
            stream,
            (self.cur_item.x0, self.cur_item.y0, self.cur_item.x1, self.cur_item.y1),
        )
        self.cur_item.add(item)

    def paint_path(
        self,
        gstate: PDFGraphicState,
        stroke: bool,
        fill: bool,
        evenodd: bool,
        path: Sequence[PathSegment],
    ) -> None:
        """Paint paths described in section 4.4 of the PDF reference manual"""
        shape = "".join(x[0] for x in path)

        if shape[:1] != "m":
            # Per PDF Reference Section 4.4.1, "path construction operators may
            # be invoked in any sequence, but the first one invoked must be m
            # or re to begin a new subpath." Since pdf2zh.six already
            # converts all `re` (rectangle) operators to their equivelent
            # `mlllh` representation, paths ingested by `.paint_path(...)` that
            # do not begin with the `m` operator are invalid.
            pass

        elif shape.count("m") > 1:
            # recurse if there are multiple m's in this shape
            for m in re.finditer(r"m[^m]+", shape):
                subpath = path[m.start(0) : m.end(0)]
                self.paint_path(gstate, stroke, fill, evenodd, subpath)

        else:
            # Although the 'h' command does not not literally provide a
            # point-position, its position is (by definition) equal to the
            # subpath's starting point.
            #
            # And, per Section 4.4's Table 4.9, all other path commands place
            # their point-position in their final two arguments. (Any preceding
            # arguments represent control points on Bézier curves.)
            raw_pts = [
                cast(Point, p[-2:] if p[0] != "h" else path[0][-2:]) for p in path
            ]
            pts = [apply_matrix_pt(self.ctm, pt) for pt in raw_pts]

            operators = [str(operation[0]) for operation in path]
            transformed_points = [
                [
                    apply_matrix_pt(self.ctm, (float(operand1), float(operand2)))
                    for operand1, operand2 in zip(operation[1::2], operation[2::2])
                ]
                for operation in path
            ]
            transformed_path = [
                cast(PathSegment, (o, *p))
                for o, p in zip(operators, transformed_points)
            ]

            if shape in {"mlh", "ml"}:
                # single line segment
                #
                # Note: 'ml', in conditional above, is a frequent anomaly
                # that we want to support.
                line = LTLine(
                    gstate.linewidth*matrix_scale(self.ctm),
                    pts[0],
                    pts[1],
                    stroke,
                    fill,
                    evenodd,
                    gstate.scolor,
                    gstate.ncolor,
                    original_path=transformed_path,
                    dashing_style=gstate.dash,
                )
                self.cur_item.add(line)

            elif shape in {"mlllh", "mllll"}:
                (x0, y0), (x1, y1), (x2, y2), (x3, y3), _ = pts

                is_closed_loop = pts[0] == pts[4]
                has_square_coordinates = (
                    x0 == x1 and y1 == y2 and x2 == x3 and y3 == y0
                ) or (y0 == y1 and x1 == x2 and y2 == y3 and x3 == x0)
                if is_closed_loop and has_square_coordinates:
                    rect = LTRect(
                        gstate.linewidth*matrix_scale(self.ctm),
                        (*pts[0], *pts[2]),
                        stroke,
                        fill,
                        evenodd,
                        gstate.scolor,
                        gstate.ncolor,
                        transformed_path,
                        gstate.dash,
                    )
                    self.cur_item.add(rect)
                else:
                    curve = LTCurve(
                        gstate.linewidth*matrix_scale(self.ctm),
                        pts,
                        stroke,
                        fill,
                        evenodd,
                        gstate.scolor,
                        gstate.ncolor,
                        transformed_path,
                        gstate.dash,
                    )
                    self.cur_item.add(curve)
            else:
                curve = LTCurve(
                    gstate.linewidth*matrix_scale(self.ctm),
                    pts,
                    stroke,
                    fill,
                    evenodd,
                    gstate.scolor,
                    gstate.ncolor,
                    transformed_path,
                    gstate.dash,
                )
                self.cur_item.add(curve)

    def render_char(
        self,
        matrix: Matrix,
        font: PDFFont,
        fontsize: float,
        scaling: float,
        rise: float,
        cid: int,
        ncs: PDFColorSpace,
        graphicstate: PDFGraphicState,
    ) -> float:
        try:
            text = font.to_unichr(cid)
            assert isinstance(text, str), str(type(text))
        except PDFUnicodeNotDefined:
            text = self.handle_undefined_char(font, cid)
        textwidth = font.char_width(cid)
        textdisp = font.char_disp(cid)
        item = LTChar(
            matrix,
            font,
            fontsize,
            scaling,
            rise,
            text,
            textwidth,
            textdisp,
            ncs,
            graphicstate,
        )
        self.cur_item.add(item)
        item.cid=cid # hack
        return item.adv

    def handle_undefined_char(self, font: PDFFont, cid: int) -> str:
        # log.debug("undefined: %r, %r", font, cid)
        return "(cid:%d)" % cid

    def receive_layout(self, ltpage: LTPage) -> None:
        pass


class PDFPageAggregator(PDFLayoutAnalyzer):
    def __init__(
        self,
        rsrcmgr: PDFResourceManager,
        pageno: int = 1,
        laparams: Optional[LAParams] = None,
    ) -> None:
        PDFLayoutAnalyzer.__init__(self, rsrcmgr, pageno=pageno, laparams=laparams)
        self.result: Optional[LTPage] = None

    def receive_layout(self, ltpage: LTPage) -> None:
        self.result = ltpage

    def get_result(self) -> LTPage:
        assert self.result is not None
        return self.result


# Some PDFConverter children support only binary I/O
IOType = TypeVar("IOType", TextIO, BinaryIO, AnyIO)


class PDFConverter(PDFLayoutAnalyzer, Generic[IOType]):
    def __init__(
        self,
        rsrcmgr: PDFResourceManager,
        outfp: IOType,
        codec: str = "utf-8",
        pageno: int = 1,
        laparams: Optional[LAParams] = None,
    ) -> None:
        PDFLayoutAnalyzer.__init__(self, rsrcmgr, pageno=pageno, laparams=laparams)
        self.outfp: IOType = outfp
        self.codec = codec
        self.outfp_binary = self._is_binary_stream(self.outfp)

    @staticmethod
    def _is_binary_stream(outfp: AnyIO) -> bool:
        """Test if an stream is binary or not"""
        if "b" in getattr(outfp, "mode", ""):
            return True
        elif hasattr(outfp, "mode"):
            # output stream has a mode, but it does not contain 'b'
            return False
        elif isinstance(outfp, io.BytesIO):
            return True
        elif isinstance(outfp, io.StringIO) or isinstance(outfp, io.TextIOBase):
            return False

        return True


class TextConverter(PDFConverter[AnyIO]):
    def __init__(
        self,
        rsrcmgr: PDFResourceManager,
        outfp: AnyIO,
        codec: str = "utf-8",
        pageno: int = 1,
        laparams: Optional[LAParams] = None,
        showpageno: bool = False,
        imagewriter: Optional[ImageWriter] = None,
        vfont: str = None,
        vchar: str = None,
        thread: int = 0,
        layout = {},
        lang_in: str = "",
        lang_out: str = "",
    ) -> None:
        super().__init__(rsrcmgr, outfp, codec=codec, pageno=pageno, laparams=laparams)
        self.showpageno = showpageno
        self.imagewriter = imagewriter
        self.vfont = vfont
        self.vchar = vchar
        self.thread = thread
        self.layout = layout
        self.lang_in = lang_in
        self.lang_out = lang_out
        self.translator=Translator()

    def write_text(self, text: str) -> None:
        text = utils.compatible_encode_method(text, self.codec, "ignore")
        if self.outfp_binary:
            cast(BinaryIO, self.outfp).write(text.encode())
        else:
            cast(TextIO, self.outfp).write(text)

    def receive_layout(self, ltpage: LTPage):
        def render(item: LTItem) -> None:
            xt=None # 上一个字符
            lt=None # 段落左边界
            rt=None # 段落右边界
            dt=None # 段落下边界
            sstk=[] # 段落文字栈
            vstk=[] # 公式符号组
            vlstk=[] # 公式线条组
            vfix=0 # 公式纵向偏移
            vbkt=0 # 段落公式括号计数
            pstk=[] # 段落属性栈
            lstk=[] # 全局线条栈
            var=[] # 公式符号组栈
            varl=[] # 公式线条组栈
            varf=[] # 公式纵向偏移栈
            vlen=[] # 公式宽度栈
            xt_ind=False # 上一个字符是否属于独立公式
            vmax=ltpage.width/4 # 行内公式最大宽度
            ops="" # 渲染结果
            def vflag(font,char): # 匹配公式（和角标）字体
                if re.match(r'\(cid:',char):
                    return True
                if self.vfont:
                    if re.match(self.vfont,font):
                        return True
                else:
                    if re.match(r'(CM[^R]|MS|XY|MT|BL|RM|EU|LA|LINE|TeX-|rsfs|txsy|wasy|.*Mono|.*Code|.*Ital|.*Sym)',font):
                        return True
                if self.vchar:
                    if re.match(self.vchar,char):
                        return True
                else:
                    if re.match(r'(\+|=|[\u0080-\u2017]|[\u2020-\ufaff])',char): # 过滤半角字符、风格连字以及 unicode 引号。公式加号和等号对应 CMR 而且不会出现在正文，公式减号对应 CMSY 不用考虑
                        return True
                return False
            ptr=0
            item=list(item)
            while ptr<len(item): # 识别文字和公式
                child=item[ptr]
                if isinstance(child, LTChar):
                    cur_v=False # 公式
                    ind_v=False # 独立公式
                    fontname=child.fontname.split('+')[-1]
                    if vflag(fontname,child.get_text()): # 识别公式和字符
                        cur_v=True
                    if child.matrix[0]==0 and child.matrix[3]==0: # 竖直段落
                        cur_v=True
                        ind_v=True
                    layout=self.layout[ltpage.pageid]
                    h,w=layout.shape # ltpage.height 可能是 fig 里面的高度，这里统一用 layout.shape
                    x0,y0,x1,y1=int(child.x0),int(h-child.y0),int(child.x1),int(h-child.y1)
                    y0=np.clip(y0,0,h-1);y1=np.clip(y1,0,h-1)
                    x0=np.clip(x0,0,w-1);x1=np.clip(x1,0,w-1)
                    # if child.get_text()=='2':
                    #     from PIL import Image, ImageDraw
                    #     img=Image.fromarray(layout*255)
                    #     img=img.convert('RGB')
                    #     draw=ImageDraw.Draw(img)
                    #     draw.rectangle([(x0,y1),(x1,y0)],ImageDraw.ImageColor.colormap['red'],ImageDraw.ImageColor.colormap['red'])
                    #     img.show()
                    #     input()
                    if layout[y0,x0] or layout[y0,x1] or layout[y1,x0] or layout[y1,x1]: # 识别图表和独立公式
                        cur_v=True
                        ind_v=True
                    if not cur_v: #and re.match(r'CMR',fontname): # 根治正文 CMR 字体的懒狗编译器，判定括号组是否属于公式
                        if vstk and child.get_text()=='(':
                            cur_v=True
                            vbkt+=1
                        if vbkt and child.get_text()==')':
                            cur_v=True
                            vbkt-=1
                    if not cur_v or (ind_v ^ xt_ind) or (vstk and (abs(child.x0-xt.x0)>vmax or abs(child.y0-xt.y0)>vmax) and not ind_v): # 公式结束、独立公式边界或公式换行截断
                        if vstk: # 公式出栈
                            sstk_bak=sstk[-1]
                            vfix_bak=vfix
                            lt_bak,rt_bak,dt_bak=lt,rt,dt
                            sstk[-1]+=f'$v{len(var)}$'
                            if child.x0>max([vch.x0 for vch in vstk]) and child.y0<vstk[0].y1 and not cur_v and vstk[0].y0-child.y0<child.size: # 行内公式修正，这里要考虑正好换行的情况
                                vfix=vstk[0].y0-child.y0
                                # print(sstk[-1],vfix)
                            var.append(vstk)
                            varl.append(vlstk)
                            varf.append(vfix)
                            vstk=[]
                            vlstk=[]
                            vfix=0
                    if not vstk: # 非公式或是公式开头
                        if not (ind_v ^ xt_ind) and xt and child.y1 > dt.y0 - min(child.size,xt.size)*0.45 and child.y0 < xt.y1 + min(child.size,xt.size): # 非独立公式边界且位于同段落，事实上不存在 ind_v 与 xt_ind 同真但 vstk 被出栈清空的情况，所以这里用 or 也是可以的
                            if child.x0 > xt.x1 + child.size*2: # 行内分离
                                lt,rt,dt=child,child,child
                                sstk.append("")
                                pstk.append([child.y0,child.x0,child.x0,child.x0,child.size,child.font,False])
                            elif child.x0 > xt.x1 + 1 and not (child.size<pstk[-1][4]*0.9): # 行内空格，小字体不加空格，因为可能会影响到下面的还原操作
                                sstk[-1]+=' '
                            elif child.x1 < xt.x0 and not (child.size<pstk[-1][4]*0.9 and xt.size<pstk[-1][4]*0.9 and abs(child.x0-xt.x0)<vmax): # 换行，这里需要考虑一下字母修饰符的情况，连续小字体不换行解决分式问题
                                if child.x0 < lt.x0 - child.size*2 or child.x0 > lt.x0 + child.size*1: # 基于初始位置的行间分离
                                    lt,rt,dt=child,child,child
                                    sstk.append("")
                                    pstk.append([child.y0,child.x0,child.x0,child.x0,child.size,child.font,False])
                                else: # 换行空格
                                    sstk[-1]+=' '
                                    pstk[-1][6]=True # 标记原文段落存在换行
                        else: # 基于纵向距离的行间分离
                            lt,rt,dt=child,child,child
                            sstk.append("")
                            pstk.append([child.y0,child.x0,child.x0,child.x0,child.size,child.font,False])
                    if not cur_v: #and re.match(r'CMR',fontname): # 根治正文 CMR 字体的懒狗编译器，这里先排除一下独立公式。因为经常会有 CMR 以外的其他小角标比如 d_model，所以这里不锁字体
                        if child.size<pstk[-1][4]*0.9: # and sstk[-1]: # 公式内文字，考虑浮点误差，如果比段落字体小，说明肯定没有重开段落，不需要再判断一次
                            cur_v=True
                            # 这里应该保证行内公式不要被空格随意打断变成两个连着的公式标记，要不然根据 xt 计算 vfix 修正的策略就不对了
                            if sstk[-1][-1]=='$': # 结尾是 $ 说明触发了上面的出栈，公式被错误打断（如果公式换行结尾会是空格），这里需要还原状态
                                sstk[-1]=sstk_bak
                                vfix=vfix_bak
                                vstk=var.pop()
                                vlstk=varl.pop()
                                varf.pop()
                                lt,rt,dt=lt_bak,rt_bak,dt_bak
                    if not cur_v: # 文字入栈
                        if child.size>pstk[-1][4]*1.1 or vflag(pstk[-1][5].fontname.split('+')[-1],'') or re.match(r'(.*Medi|.*Bold)',pstk[-1][5].fontname.split('+')[-1],re.IGNORECASE): # 小字体、公式或粗体开头，后续接文字，需要校正字体
                            pstk[-1][0]-=child.size-pstk[-1][4]
                            pstk[-1][4]=child.size
                            pstk[-1][5]=child.font
                        sstk[-1]+=child.get_text()
                    else: # 公式入栈
                        # 可能是 CMR 角标，需要在完全确定 cur_v 之后再计算修正，有些下角标可能需要向下的修正
                        if not vstk and sstk[-1]: # 公式开头，不是段落开头
                            if child.x0>xt.x0 and child.y1>xt.y0: # and cur_v: # and child.y0-xt.y0<xt.size: # 行内公式修正，前面已经判定过位于同一段落，所以不需要限制 y 范围
                                vfix=child.y0-xt.y0
                        vstk.append(child)
                    # 更新段落边界，段落内换行之后可能是公式开头，如果不更新 dt 后面换行检测会出错
                    if child.x0<lt.x0:
                        pstk[-1][2]=child.x0
                        lt=child
                    if child.x1>rt.x1:
                        pstk[-1][3]=child.x1
                        rt=child
                    if child.y0<dt.y0:
                        dt=child
                    xt=child
                    xt_ind=ind_v
                elif isinstance(child, LTFigure): # 图表
                    pass
                elif isinstance(child, LTLine): # 线条
                    if vstk and abs(child.x0-xt.x0)<vmax and child.x1-child.x0<vmax and child.y0==child.y1 or xt_ind: # 公式线条
                        vlstk.append(child)
                    else: # 全局线条
                        lstk.append(child)
                else:
                    # print(child)
                    pass
                ptr+=1
            # 处理结尾
            if vstk: # 公式出栈
                sstk[-1]+=f'$v{len(var)}$'
                var.append(vstk)
                varl.append(vlstk)
                varf.append(vfix)
            log.debug('\n==========[VSTACK]==========\n')
            for id,v in enumerate(var): # 计算公式宽度
                l=max([vch.x1 for vch in v])-v[0].x0
                log.debug(f'< {l:.1f} {v[0].x0:.1f} {v[0].y0:.1f} {v[0].cid} {v[0].fontname} {len(varl[id])} > $v{id}$ = {"".join([ch.get_text() for ch in v])}')
                vlen.append(l)
            log.debug('\n==========[SSTACK]==========\n')
            hash_key=cache.deterministic_hash("PDFMathTranslate")
            cache.create_cache(hash_key)
            @retry
            def worker(s): # 多线程翻译
                try:
                    hash_key_paragraph = cache.deterministic_hash((s,self.lang_in,self.lang_out))
                    new = cache.load_paragraph(hash_key, hash_key_paragraph) # 查询缓存
                    if new is None:
                        new=self.translator.translate(s,self.lang_out,self.lang_in)
                        new=remove_control_characters(new)
                        cache.write_paragraph(hash_key, hash_key_paragraph, new)
                    return new
                except BaseException as e:
                    log.exception(e,exc_info=False)
                    raise e
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.thread) as executor:
                news = list(executor.map(worker, sstk))
            def raw_string(fcur,cstk): # 编码字符串
                if isinstance(self.fontmap[fcur],PDFCIDFont): # 判断编码长度
                    return "".join(["%04x" % ord(c) for c in cstk])
                else:
                    return "".join(["%02x" % ord(c) for c in cstk])
            _x,_y=0,0
            for id,new in enumerate(news): # 排版文字和公式
                tx=x=pstk[id][1];y=pstk[id][0];lt=pstk[id][2];rt=pstk[id][3];ptr=0;size=pstk[id][4];font=pstk[id][5];lb=pstk[id][6] # 段落属性
                cstk='' # 单行文字栈
                fcur=fcur_=None # 单行字体
                log.debug(f"< {y} {x} {lt} {rt} {size} {font.fontname} {lb} > {sstk[id]} | {new}")
                while True:
                    if ptr==len(new): # 到达段落结尾
                        if cstk:
                            ops+=f'/{fcur} {size} Tf 1 0 0 1 {tx} {y} Tm [<{raw_string(fcur,cstk)}>] TJ '
                        break
                    vy_regex=re.match(r'\$?\s*v([\d\s]+)\$',new[ptr:],re.IGNORECASE) # 匹配 $vn$ 公式标记，前面的 $ 有的时候会被丢掉
                    mod=False # 当前公式是否为文字修饰符
                    if vy_regex: # 加载公式
                        ptr+=len(vy_regex.group(0))
                        try:
                            vid=int(vy_regex.group(1).replace(' ',''))
                            adv=vlen[vid]
                        except:
                            continue # 翻译器可能会自动补个越界的公式标记
                        if len(var[vid])==1 and unicodedata.category(var[vid][0].get_text()[0]) in ['Lm','Sk','Mn']: # 文字修饰符，get_text 可能返回 cid，这里截断一下
                            mod=True
                    else: # 加载文字
                        ch=new[ptr]
                        # if font.char_width(ord(ch)):
                        fcur_=None
                        try:
                            # 1.有些字体会设置非 0 缺省宽度，所以这里直接查一下宽度字典
                            # 2.有些字体不使用标准 unicode 编码，这里校验一下
                            if font.widths.get(ord(ch)) and font.to_unichr(ord(ch))==ch:
                                fcur_=font.fontid # 原字体
                        except:
                            pass
                        if fcur_==None:
                            if re.match(r'[\u0000-\u007f]',ch): # 半角符号
                                fcur_='tiro' # 默认英文字体
                            else:
                                fcur_='china-ss' # 默认中文字体
                        # print(font.fontid,fcur_,ch,font.char_width(ord(ch)))
                        adv=self.fontmap[fcur_].char_width(ord(ch))*size
                        ptr+=1
                    if fcur_!=fcur or vy_regex or x+adv>rt+0.1*size: # 输出文字缓冲区：1.字体更新 2.插入公式 3.到达右边界（可能一整行都被符号化，这里需要考虑浮点误差）
                        if cstk:
                            ops+=f'/{fcur} {size} Tf 1 0 0 1 {tx} {y} Tm [<{raw_string(fcur,cstk)}>] TJ '
                            cstk=''
                    if lb and x+adv>rt+0.1*size: # 到达右边界且原文段落存在换行
                        x=lt
                        lang_space={'zh-CN':1.4,'zh-TW':1.4,'ja':1.1,'ko':1.2}
                        y-=size*lang_space.get(self.lang_out,1.4)
                    if vy_regex: # 插入公式
                        fix=0
                        if fcur!=None: # 段落内公式修正纵向偏移
                            fix=varf[vid]
                        for vch in var[vid]: # 排版公式字符
                            vc=chr(vch.cid)
                            ops+=f"/{vch.font.fontid} {vch.size} Tf 1 0 0 1 {x+vch.x0-var[vid][0].x0} {fix+y+vch.y0-var[vid][0].y0} Tm [<{raw_string(vch.font.fontid,vc)}>] TJ "
                            if log.isEnabledFor(logging.DEBUG):
                                lstk.append(LTLine(0.1,(_x,_y),(x+vch.x0-var[vid][0].x0,fix+y+vch.y0-var[vid][0].y0)))
                                _x,_y=x+vch.x0-var[vid][0].x0,fix+y+vch.y0-var[vid][0].y0
                        for l in varl[vid]: # 排版公式线条
                            if l.linewidth<5: # hack
                                ops+=f"ET q 1 0 0 1 {l.pts[0][0]+x-var[vid][0].x0} {l.pts[0][1]+fix+y-var[vid][0].y0} cm [] 0 d 0 J {l.linewidth} w 0 0 m {l.pts[1][0]-l.pts[0][0]} {l.pts[1][1]-l.pts[0][1]} l S Q BT "
                    else: # 插入文字缓冲区
                        if not cstk: # 单行开头
                            tx=x
                            if x==lt and ch==' ': # 消除段落换行空格
                                adv=0
                            else:
                                cstk+=ch
                        else:
                            cstk+=ch
                    if mod: # 文字修饰符
                        adv=0
                    fcur=fcur_
                    x+=adv
                    if log.isEnabledFor(logging.DEBUG):
                        lstk.append(LTLine(0.1,(_x,_y),(x,y)))
                        _x,_y=x,y
            for l in lstk: # 排版全局线条
                if l.linewidth<5: # hack
                    ops+=f"ET q 1 0 0 1 {l.pts[0][0]} {l.pts[0][1]} cm [] 0 d 0 J {l.linewidth} w 0 0 m {l.pts[1][0]-l.pts[0][0]} {l.pts[1][1]-l.pts[0][1]} l S Q BT "
            ops=f'BT {ops}ET '
            return ops
        ops=render(ltpage)
        return ops

    # Some dummy functions to save memory/CPU when all that is wanted
    # is text.  This stops all the image and drawing output from being
    # recorded and taking up RAM.
    def render_image(self, name: str, stream: PDFStream) -> None:
        if self.imagewriter is not None:
            PDFConverter.render_image(self, name, stream)

    # def paint_path(
    #     self,
    #     gstate: PDFGraphicState,
    #     stroke: bool,
    #     fill: bool,
    #     evenodd: bool,
    #     path: Sequence[PathSegment],
    # ) -> None:
    #     pass


class HTMLConverter(PDFConverter[AnyIO]):
    RECT_COLORS = {
        "figure": "yellow",
        "textline": "magenta",
        "textbox": "cyan",
        "textgroup": "red",
        "curve": "black",
        "page": "gray",
    }

    TEXT_COLORS = {
        "textbox": "blue",
        "char": "black",
    }

    def __init__(
        self,
        rsrcmgr: PDFResourceManager,
        outfp: AnyIO,
        codec: str = "utf-8",
        pageno: int = 1,
        laparams: Optional[LAParams] = None,
        scale: float = 1,
        fontscale: float = 1.0,
        layoutmode: str = "normal",
        showpageno: bool = True,
        pagemargin: int = 50,
        imagewriter: Optional[ImageWriter] = None,
        debug: int = 0,
        rect_colors: Optional[Dict[str, str]] = None,
        text_colors: Optional[Dict[str, str]] = None,
    ) -> None:
        PDFConverter.__init__(
            self,
            rsrcmgr,
            outfp,
            codec=codec,
            pageno=pageno,
            laparams=laparams,
        )

        # write() assumes a codec for binary I/O, or no codec for text I/O.
        if self.outfp_binary and not self.codec:
            raise PDFValueError("Codec is required for a binary I/O output")
        if not self.outfp_binary and self.codec:
            raise PDFValueError("Codec must not be specified for a text I/O output")

        if text_colors is None:
            text_colors = {"char": "black"}
        if rect_colors is None:
            rect_colors = {"curve": "black", "page": "gray"}

        self.scale = scale
        self.fontscale = fontscale
        self.layoutmode = layoutmode
        self.showpageno = showpageno
        self.pagemargin = pagemargin
        self.imagewriter = imagewriter
        self.rect_colors = rect_colors
        self.text_colors = text_colors
        if debug:
            self.rect_colors.update(self.RECT_COLORS)
            self.text_colors.update(self.TEXT_COLORS)
        self._yoffset: float = self.pagemargin
        self._font: Optional[Tuple[str, float]] = None
        self._fontstack: List[Optional[Tuple[str, float]]] = []
        self.write_header()

    def write(self, text: str) -> None:
        if self.codec:
            cast(BinaryIO, self.outfp).write(text.encode(self.codec))
        else:
            cast(TextIO, self.outfp).write(text)

    def write_header(self) -> None:
        self.write("<html><head>\n")
        if self.codec:
            s = (
                '<meta http-equiv="Content-Type" content="text/html; '
                'charset=%s">\n' % self.codec
            )
        else:
            s = '<meta http-equiv="Content-Type" content="text/html">\n'
        self.write(s)
        self.write("</head><body>\n")

    def write_footer(self) -> None:
        page_links = [f'<a href="#{i}">{i}</a>' for i in range(1, self.pageno)]
        s = '<div style="position:absolute; top:0px;">Page: %s</div>\n' % ", ".join(
            page_links,
        )
        self.write(s)
        self.write("</body></html>\n")

    def write_text(self, text: str) -> None:
        self.write(enc(text))

    def place_rect(
        self,
        color: str,
        borderwidth: int,
        x: float,
        y: float,
        w: float,
        h: float,
    ) -> None:
        color2 = self.rect_colors.get(color)
        if color2 is not None:
            s = (
                '<span style="position:absolute; border: %s %dpx solid; '
                'left:%dpx; top:%dpx; width:%dpx; height:%dpx;"></span>\n'
                % (
                    color2,
                    borderwidth,
                    x * self.scale,
                    (self._yoffset - y) * self.scale,
                    w * self.scale,
                    h * self.scale,
                )
            )
            self.write(s)

    def place_border(self, color: str, borderwidth: int, item: LTComponent) -> None:
        self.place_rect(color, borderwidth, item.x0, item.y1, item.width, item.height)

    def place_image(
        self,
        item: LTImage,
        borderwidth: int,
        x: float,
        y: float,
        w: float,
        h: float,
    ) -> None:
        if self.imagewriter is not None:
            name = self.imagewriter.export_image(item)
            s = (
                '<img src="%s" border="%d" style="position:absolute; '
                'left:%dpx; top:%dpx;" width="%d" height="%d" />\n'
                % (
                    enc(name),
                    borderwidth,
                    x * self.scale,
                    (self._yoffset - y) * self.scale,
                    w * self.scale,
                    h * self.scale,
                )
            )
            self.write(s)

    def place_text(
        self,
        color: str,
        text: str,
        x: float,
        y: float,
        size: float,
    ) -> None:
        color2 = self.text_colors.get(color)
        if color2 is not None:
            s = (
                '<span style="position:absolute; color:%s; left:%dpx; '
                'top:%dpx; font-size:%dpx;">'
                % (
                    color2,
                    x * self.scale,
                    (self._yoffset - y) * self.scale,
                    size * self.scale * self.fontscale,
                )
            )
            self.write(s)
            self.write_text(text)
            self.write("</span>\n")

    def begin_div(
        self,
        color: str,
        borderwidth: int,
        x: float,
        y: float,
        w: float,
        h: float,
        writing_mode: str = "False",
    ) -> None:
        self._fontstack.append(self._font)
        self._font = None
        s = (
            '<div style="position:absolute; border: %s %dpx solid; '
            "writing-mode:%s; left:%dpx; top:%dpx; width:%dpx; "
            'height:%dpx;">'
            % (
                color,
                borderwidth,
                writing_mode,
                x * self.scale,
                (self._yoffset - y) * self.scale,
                w * self.scale,
                h * self.scale,
            )
        )
        self.write(s)

    def end_div(self, color: str) -> None:
        if self._font is not None:
            self.write("</span>")
        self._font = self._fontstack.pop()
        self.write("</div>")

    def put_text(self, text: str, fontname: str, fontsize: float) -> None:
        font = (fontname, fontsize)
        if font != self._font:
            if self._font is not None:
                self.write("</span>")
            # Remove subset tag from fontname, see PDF Reference 5.5.3
            fontname_without_subset_tag = fontname.split("+")[-1]
            self.write(
                '<span style="font-family: %s; font-size:%dpx">'
                % (fontname_without_subset_tag, fontsize * self.scale * self.fontscale),
            )
            self._font = font
        self.write_text(text)

    def put_newline(self) -> None:
        self.write("<br>")

    def receive_layout(self, ltpage: LTPage) -> None:
        def show_group(item: Union[LTTextGroup, TextGroupElement]) -> None:
            if isinstance(item, LTTextGroup):
                self.place_border("textgroup", 1, item)
                for child in item:
                    show_group(child)

        def render(item: LTItem) -> None:
            child: LTItem
            if isinstance(item, LTPage):
                self._yoffset += item.y1
                self.place_border("page", 1, item)
                if self.showpageno:
                    self.write(
                        '<div style="position:absolute; top:%dpx;">'
                        % ((self._yoffset - item.y1) * self.scale),
                    )
                    self.write(
                        f'<a name="{item.pageid}">Page {item.pageid}</a></div>\n',
                    )
                for child in item:
                    render(child)
                if item.groups is not None:
                    for group in item.groups:
                        show_group(group)
            elif isinstance(item, LTCurve):
                self.place_border("curve", 1, item)
            elif isinstance(item, LTFigure):
                self.begin_div("figure", 1, item.x0, item.y1, item.width, item.height)
                for child in item:
                    render(child)
                self.end_div("figure")
            elif isinstance(item, LTImage):
                self.place_image(item, 1, item.x0, item.y1, item.width, item.height)
            elif self.layoutmode == "exact":
                if isinstance(item, LTTextLine):
                    self.place_border("textline", 1, item)
                    for child in item:
                        render(child)
                elif isinstance(item, LTTextBox):
                    self.place_border("textbox", 1, item)
                    self.place_text(
                        "textbox",
                        str(item.index + 1),
                        item.x0,
                        item.y1,
                        20,
                    )
                    for child in item:
                        render(child)
                elif isinstance(item, LTChar):
                    self.place_border("char", 1, item)
                    self.place_text(
                        "char",
                        item.get_text(),
                        item.x0,
                        item.y1,
                        item.size,
                    )
            elif isinstance(item, LTTextLine):
                for child in item:
                    render(child)
                if self.layoutmode != "loose":
                    self.put_newline()
            elif isinstance(item, LTTextBox):
                self.begin_div(
                    "textbox",
                    1,
                    item.x0,
                    item.y1,
                    item.width,
                    item.height,
                    item.get_writing_mode(),
                )
                for child in item:
                    render(child)
                self.end_div("textbox")
            elif isinstance(item, LTChar):
                fontname = make_compat_str(item.fontname)
                self.put_text(item.get_text(), fontname, item.size)
            elif isinstance(item, LTText):
                self.write_text(item.get_text())

        render(ltpage)
        self._yoffset += self.pagemargin

    def close(self) -> None:
        self.write_footer()


class XMLConverter(PDFConverter[AnyIO]):
    CONTROL = re.compile("[\x00-\x08\x0b-\x0c\x0e-\x1f]")

    def __init__(
        self,
        rsrcmgr: PDFResourceManager,
        outfp: AnyIO,
        codec: str = "utf-8",
        pageno: int = 1,
        laparams: Optional[LAParams] = None,
        imagewriter: Optional[ImageWriter] = None,
        stripcontrol: bool = False,
    ) -> None:
        PDFConverter.__init__(
            self,
            rsrcmgr,
            outfp,
            codec=codec,
            pageno=pageno,
            laparams=laparams,
        )

        # write() assumes a codec for binary I/O, or no codec for text I/O.
        if self.outfp_binary == (not self.codec):
            raise PDFValueError("Codec is required for a binary I/O output")

        self.imagewriter = imagewriter
        self.stripcontrol = stripcontrol
        self.write_header()

    def write(self, text: str) -> None:
        if self.codec:
            cast(BinaryIO, self.outfp).write(text.encode(self.codec))
        else:
            cast(TextIO, self.outfp).write(text)

    def write_header(self) -> None:
        if self.codec:
            self.write('<?xml version="1.0" encoding="%s" ?>\n' % self.codec)
        else:
            self.write('<?xml version="1.0" ?>\n')
        self.write("<pages>\n")

    def write_footer(self) -> None:
        self.write("</pages>\n")

    def write_text(self, text: str) -> None:
        if self.stripcontrol:
            text = self.CONTROL.sub("", text)
        self.write(enc(text))

    def receive_layout(self, ltpage: LTPage) -> None:
        def show_group(item: LTItem) -> None:
            if isinstance(item, LTTextBox):
                self.write(
                    '<textbox id="%d" bbox="%s" />\n'
                    % (item.index, bbox2str(item.bbox)),
                )
            elif isinstance(item, LTTextGroup):
                self.write('<textgroup bbox="%s">\n' % bbox2str(item.bbox))
                for child in item:
                    show_group(child)
                self.write("</textgroup>\n")

        def render(item: LTItem) -> None:
            child: LTItem
            if isinstance(item, LTPage):
                s = '<page id="%s" bbox="%s" rotate="%d">\n' % (
                    item.pageid,
                    bbox2str(item.bbox),
                    item.rotate,
                )
                self.write(s)
                for child in item:
                    render(child)
                if item.groups is not None:
                    self.write("<layout>\n")
                    for group in item.groups:
                        show_group(group)
                    self.write("</layout>\n")
                self.write("</page>\n")
            elif isinstance(item, LTLine):
                s = '<line linewidth="%d" bbox="%s" />\n' % (
                    item.linewidth,
                    bbox2str(item.bbox),
                )
                self.write(s)
            elif isinstance(item, LTRect):
                s = '<rect linewidth="%d" bbox="%s" />\n' % (
                    item.linewidth,
                    bbox2str(item.bbox),
                )
                self.write(s)
            elif isinstance(item, LTCurve):
                s = '<curve linewidth="%d" bbox="%s" pts="%s"/>\n' % (
                    item.linewidth,
                    bbox2str(item.bbox),
                    item.get_pts(),
                )
                self.write(s)
            elif isinstance(item, LTFigure):
                s = f'<figure name="{item.name}" bbox="{bbox2str(item.bbox)}">\n'
                self.write(s)
                for child in item:
                    render(child)
                self.write("</figure>\n")
            elif isinstance(item, LTTextLine):
                self.write('<textline bbox="%s">\n' % bbox2str(item.bbox))
                for child in item:
                    render(child)
                self.write("</textline>\n")
            elif isinstance(item, LTTextBox):
                wmode = ""
                if isinstance(item, LTTextBoxVertical):
                    wmode = ' wmode="vertical"'
                s = '<textbox id="%d" bbox="%s"%s>\n' % (
                    item.index,
                    bbox2str(item.bbox),
                    wmode,
                )
                self.write(s)
                for child in item:
                    render(child)
                self.write("</textbox>\n")
            elif isinstance(item, LTChar):
                s = (
                    '<text font="%s" bbox="%s" colourspace="%s" '
                    'ncolour="%s" size="%.3f">'
                    % (
                        enc(item.fontname),
                        bbox2str(item.bbox),
                        item.ncs.name,
                        item.graphicstate.ncolor,
                        item.size,
                    )
                )
                self.write(s)
                self.write_text(item.get_text())
                self.write("</text>\n")
            elif isinstance(item, LTText):
                self.write("<text>%s</text>\n" % item.get_text())
            elif isinstance(item, LTImage):
                if self.imagewriter is not None:
                    name = self.imagewriter.export_image(item)
                    self.write(
                        '<image src="%s" width="%d" height="%d" />\n'
                        % (enc(name), item.width, item.height),
                    )
                else:
                    self.write(
                        '<image width="%d" height="%d" />\n'
                        % (item.width, item.height),
                    )
            else:
                assert False, str(("Unhandled", item))

        render(ltpage)

    def close(self) -> None:
        self.write_footer()


class HOCRConverter(PDFConverter[AnyIO]):
    """Extract an hOCR representation from explicit text information within a PDF."""

    #   Where text is being extracted from a variety of types of PDF within a
    #   business process, those PDFs where the text is only present in image
    #   form will need to be analysed using an OCR tool which will typically
    #   output hOCR. This converter extracts the explicit text information from
    #   those PDFs that do have it and uses it to genxerate a basic hOCR
    #   representation that is designed to be used in conjunction with the image
    #   of the PDF in the same way as genuine OCR output would be, but without the
    #   inevitable OCR errors.

    #   The converter does not handle images, diagrams or text colors.

    #   In the examples processed by the contributor it was necessary to set
    #   LAParams.all_texts to True.

    CONTROL = re.compile(r"[\x00-\x08\x0b-\x0c\x0e-\x1f]")

    def __init__(
        self,
        rsrcmgr: PDFResourceManager,
        outfp: AnyIO,
        codec: str = "utf8",
        pageno: int = 1,
        laparams: Optional[LAParams] = None,
        stripcontrol: bool = False,
    ):
        PDFConverter.__init__(
            self,
            rsrcmgr,
            outfp,
            codec=codec,
            pageno=pageno,
            laparams=laparams,
        )
        self.stripcontrol = stripcontrol
        self.within_chars = False
        self.write_header()

    def bbox_repr(self, bbox: Rect) -> str:
        (in_x0, in_y0, in_x1, in_y1) = bbox
        # PDF y-coordinates are the other way round from hOCR coordinates
        out_x0 = int(in_x0)
        out_y0 = int(self.page_bbox[3] - in_y1)
        out_x1 = int(in_x1)
        out_y1 = int(self.page_bbox[3] - in_y0)
        return f"bbox {out_x0} {out_y0} {out_x1} {out_y1}"

    def write(self, text: str) -> None:
        if self.codec:
            encoded_text = text.encode(self.codec)
            cast(BinaryIO, self.outfp).write(encoded_text)
        else:
            cast(TextIO, self.outfp).write(text)

    def write_header(self) -> None:
        if self.codec:
            self.write(
                "<html xmlns='http://www.w3.org/1999/xhtml' "
                "xml:lang='en' lang='en' charset='%s'>\n" % self.codec,
            )
        else:
            self.write(
                "<html xmlns='http://www.w3.org/1999/xhtml' "
                "xml:lang='en' lang='en'>\n",
            )
        self.write("<head>\n")
        self.write("<title></title>\n")
        self.write(
            "<meta http-equiv='Content-Type' content='text/html;charset=utf-8' />\n",
        )
        self.write(
            "<meta name='ocr-system' content='pdf2zh.six HOCR Converter' />\n",
        )
        self.write(
            "  <meta name='ocr-capabilities'"
            " content='ocr_page ocr_block ocr_line ocrx_word'/>\n",
        )
        self.write("</head>\n")
        self.write("<body>\n")

    def write_footer(self) -> None:
        self.write("<!-- comment in the following line to debug -->\n")
        self.write(
            "<!--script src='https://unpkg.com/hocrjs'></script--></body></html>\n",
        )

    def write_text(self, text: str) -> None:
        if self.stripcontrol:
            text = self.CONTROL.sub("", text)
        self.write(text)

    def write_word(self) -> None:
        if len(self.working_text) > 0:
            bold_and_italic_styles = ""
            if "Italic" in self.working_font:
                bold_and_italic_styles = "font-style: italic; "
            if "Bold" in self.working_font:
                bold_and_italic_styles += "font-weight: bold; "
            self.write(
                "<span style='font:\"%s\"; font-size:%d; %s' "
                "class='ocrx_word' title='%s; x_font %s; "
                "x_fsize %d'>%s</span>"
                % (
                    (
                        self.working_font,
                        self.working_size,
                        bold_and_italic_styles,
                        self.bbox_repr(self.working_bbox),
                        self.working_font,
                        self.working_size,
                        self.working_text.strip(),
                    )
                ),
            )
        self.within_chars = False

    def receive_layout(self, ltpage: LTPage) -> None:
        def render(item: LTItem) -> None:
            if self.within_chars and isinstance(item, LTAnno):
                self.write_word()
            if isinstance(item, LTPage):
                self.page_bbox = item.bbox
                self.write(
                    "<div class='ocr_page' id='%s' title='%s'>\n"
                    % (item.pageid, self.bbox_repr(item.bbox)),
                )
                for child in item:
                    render(child)
                self.write("</div>\n")
            elif isinstance(item, LTTextLine):
                self.write(
                    "<span class='ocr_line' title='%s'>" % (self.bbox_repr(item.bbox)),
                )
                for child_line in item:
                    render(child_line)
                self.write("</span>\n")
            elif isinstance(item, LTTextBox):
                self.write(
                    "<div class='ocr_block' id='%d' title='%s'>\n"
                    % (item.index, self.bbox_repr(item.bbox)),
                )
                for child in item:
                    render(child)
                self.write("</div>\n")
            elif isinstance(item, LTChar):
                if not self.within_chars:
                    self.within_chars = True
                    self.working_text = item.get_text()
                    self.working_bbox = item.bbox
                    self.working_font = item.fontname
                    self.working_size = item.size
                elif len(item.get_text().strip()) == 0:
                    self.write_word()
                    self.write(item.get_text())
                else:
                    if (
                        self.working_bbox[1] != item.bbox[1]
                        or self.working_font != item.fontname
                        or self.working_size != item.size
                    ):
                        self.write_word()
                        self.working_bbox = item.bbox
                        self.working_font = item.fontname
                        self.working_size = item.size
                    self.working_text += item.get_text()
                    self.working_bbox = (
                        self.working_bbox[0],
                        self.working_bbox[1],
                        item.bbox[2],
                        self.working_bbox[3],
                    )

        render(ltpage)

    def close(self) -> None:
        self.write_footer()
