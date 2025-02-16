from collections import defaultdict
from typing import Dict
from enum import Enum

from pdfminer.pdfinterp import PDFGraphicState, PDFResourceManager
from pdfminer.pdffont import PDFCIDFont
from pdfminer.converter import PDFConverter
from pdfminer.pdffont import PDFUnicodeNotDefined
from pdfminer.utils import apply_matrix_pt, mult_matrix
from pdfminer.layout import (
    LTChar,
    LTFigure,
    LTLine,
    LTRect,
    LTPage,
)
import logging
import re
import concurrent.futures
import numpy as np
import unicodedata
from string import Template
from tenacity import retry, wait_fixed
from pdf2zh.translator import (
    AzureOpenAITranslator,
    BaseTranslator,
    GoogleTranslator,
    BingTranslator,
    DeepLTranslator,
    DeepLXTranslator,
    OllamaTranslator,
    OpenAITranslator,
    ZhipuTranslator,
    ModelScopeTranslator,
    SiliconTranslator,
    GeminiTranslator,
    AzureTranslator,
    TencentTranslator,
    DifyTranslator,
    AnythingLLMTranslator,
    XinferenceTranslator,
    ArgosTranslator,
    GorkTranslator,
    GroqTranslator,
    DeepseekTranslator,
    OpenAIlikedTranslator,
    QwenMtTranslator,
)
from pymupdf import Font

log = logging.getLogger(__name__)


class PDFConverterEx(PDFConverter):
    def __init__(
        self,
        rsrcmgr: PDFResourceManager,
    ) -> None:
        PDFConverter.__init__(self, rsrcmgr, None, "utf-8", 1, None)

    def begin_page(self, page, ctm) -> None:
        # 重载替换 cropbox
        (x0, y0, x1, y1) = page.cropbox
        (x0, y0) = apply_matrix_pt(ctm, (x0, y0))
        (x1, y1) = apply_matrix_pt(ctm, (x1, y1))
        mediabox = (0, 0, abs(x0 - x1), abs(y0 - y1))
        self.cur_item = LTPage(page.pageno, mediabox)

    def end_page(self, page):
        # 重载返回指令流
        return self.receive_layout(self.cur_item)

    def begin_figure(self, name, bbox, matrix) -> None:
        # 重载设置 pageid
        self._stack.append(self.cur_item)
        self.cur_item = LTFigure(name, bbox, mult_matrix(matrix, self.ctm))
        self.cur_item.pageid = self._stack[-1].pageid

    def end_figure(self, _: str) -> None:
        # 重载返回指令流
        fig = self.cur_item
        assert isinstance(self.cur_item, LTFigure), str(type(self.cur_item))
        self.cur_item = self._stack.pop()
        self.cur_item.add(fig)
        return self.receive_layout(fig)

    def render_char(
        self,
        matrix,
        font,
        fontsize: float,
        scaling: float,
        rise: float,
        cid: int,
        ncs,
        graphicstate: PDFGraphicState,
    ) -> float:
        # 重载设置 cid 和 font
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
        item.cid = cid  # hack 插入原字符编码
        item.font = font  # hack 插入原字符字体
        return item.adv

def frag_to_string(frag):
    # for debug purpose
    return "".join([ch.get_text() for ch in frag])
                                                                                  
class Paragraph:
    def __init__(self, y, x, x0, x1, y0, y1, fontname, size, brk):
        self.y: float = y  # 初始纵坐标
        self.x: float = x  # 初始横坐标
        self.x0: float = x0  # 左边界
        self.x1: float = x1  # 右边界
        self.y0: float = y0  # 上边界
        self.y1: float = y1  # 下边界
        self.size: float = size  # 字体大小
        self.brk: bool = brk  # 换行标记
        self.fontname: str = fontname  # 字体名

MAGIC = 5
EPSILON = 0.05

def has_math_character(frag: list[LTChar]) -> bool:
    for ltchar in frag:
        text = ltchar.get_text()
        if len(text) != 1:
            return True
        # check whether unicode of the character in range U+1D400 to U+1D7FF
        if 0x1D400 <= ord(text) <= 0x1D7FF:
            return True
        if 0x2200 <= ord(text) <= 0x22FF:
            return True
    return False

class CLSContent:
    def __init__(self, ltpage):
        self.max_x = ltpage.x1
        self.max_y = ltpage.y1
        self.lt_chars = []
        self.lt_lines = []  # including LTLine and LTRect
        self.var = []
        self.varl = []
        self.varf = []
        self.sstk = []
        self.pstk = []
        self.x0 = 0
        self.x1 = 0
        self.y0 = 0
        self.y1 = 0

    def add_char(self, lt_char):
        self.lt_chars.append(lt_char)
    
    def add_line(self, lt_line):
        self.lt_lines.append(lt_line)

    def finish_add(self):
        if len(self.lt_chars) == 0 and len(self.lt_lines) == 0:
            self.x0 = self.x1 = self.y0 = self.y1 = 0
        else:
            self.x0 = min([c.x0 for c in self.lt_chars] + [c.x0 for c in self.lt_lines])
            self.x1 = max([c.x1 for c in self.lt_chars] + [c.x1 for c in self.lt_lines])
            self.y0 = min([c.y0 for c in self.lt_chars] + [c.y0 for c in self.lt_lines])
            self.y1 = max([c.y1 for c in self.lt_chars] + [c.y1 for c in self.lt_lines])
 
    def build_fragments(self):
        '''
        For consecutive characters with the same font, size, and y0, and a very small space between characters,
        they are considered to belong to the same fragment.
        Return: list[frag], each frag is list[LTChar]
        '''
        frags = []
        if len(self.lt_chars) == 0:
            return frags
        current_frag = [self.lt_chars[0]]
        for i in range(1, len(self.lt_chars)):
            if (self.lt_chars[i].fontname == current_frag[-1].fontname
                and self.lt_chars[i].size == current_frag[-1].size
                and self.lt_chars[i].y0 == current_frag[-1].y0
                and self.lt_chars[i].x0 - current_frag[-1].x1 < current_frag[-1].x1 - current_frag[-1].x0):
                current_frag.append(self.lt_chars[i])
            else:
                frags.append(current_frag)
                current_frag = [self.lt_chars[i]]
        frags.append(current_frag)
        return frags

    def voting(self, frags):
        '''
        find out which fontname and size have most characters. This fontname/size are treated as
        plain text fontname/size.
        '''
        fontname_size = defaultdict(int)
        for frag in frags:
            if len(frag) == 0:
                continue
            fontname = frag[0].fontname
            size = frag[0].size
            fontname_size[(fontname, size)] += len([ch for ch in frag if ch.get_text().isalpha()])
        return max(fontname_size, key=fontname_size.get)

    def split_fragments(self, frags: list[list[LTChar]], fontname: str, size: float) -> tuple[list[list[list[LTChar]]], list[list[LTChar]]]:
        '''
        Decide what is text and what is variable. And put text in lines.
        returning tuple(lines, list[var_frag])
        lines: list[text_frag]
        text_frag, var_frag: list[LTChar]
        '''
        lines = []
        var_frags = []
        y0 = -1
        for frag in frags:
            is_text = False
            if abs(frag[0].size - size) < size*0.1:  # similar size
                if (frag[0].fontname != fontname
                    and (
                        re.match(                                            # latex 字体
                        r"(CM[^R]|MS.M|XY|MT|BL|RM|EU|LA|RS|LINE|LCIRCLE|TeX-|rsfs|txsy|wasy|stmary|.*Mono|.*Code|.*Ital|.*Sym|.*Math)",
                        frag[0].fontname)
                        or has_math_character(frag)
                    )):
                    is_text = False
                else:
                    is_text = True

            if is_text:
                if y0 == -1 or frag[0].y0 < y0 - size:  # new lines
                    lines.append([frag])
                    y0 = frag[0].y0
                elif abs(frag[0].y0 - y0) < EPSILON:  # same line as previous
                    lines[-1].append(frag)
                else:  # not aligned. treat it as var
                    var_frags.append(frag)
            else:
                var_frags.append(frag)
        return lines, var_frags
 
    def process(self, next_var):
        frags = self.build_fragments()
        if len(frags) == 0:
            return
        fontname, size = self.voting(frags)
        lines, var_frags = self.split_fragments(frags, fontname, size)

        # find out position for each var frag and line/rect, relative to text.
        # position is defined as a tuple: (line, index), means the var frag should be
        # put at the before index-th text frag of line-th line.
        result = defaultdict(list)  # position -> list[LTChar|LTLine|LTRect]
        def get_y0_y1_x0_x1(frag_or_line):
            if isinstance(frag_or_line, list):
                return frag_or_line[0].y0, frag_or_line[-1].y1, frag_or_line[0].x0, frag_or_line[-1].x1
            else:
                return frag_or_line.y0, frag_or_line.y1, frag_or_line.x0, frag_or_line.x1
            
        for var_frag in var_frags + self.lt_lines:
            var_frag_y0, var_frag_y1, var_frag_x0, var_frag_x1 = get_y0_y1_x0_x1(var_frag)
            position = None
            for line_number, line in enumerate(lines):  # from top to bottom
                line_y0, line_y1 = line[0][0].y0, line[0][0].y1
                # check overlap
                if var_frag_y0 > line_y0 or var_frag_y1 >= line_y0 + size/2:
                    # must in this line.
                    index = next((i for i,text_frag in enumerate(line) if var_frag_x0 < text_frag[0].x0), len(line))
                    position = (line_number, index)
                    break  # breaking the loop for lines
                else:
                    if line_number < len(lines) - 1 and var_frag_y0 + size/2 > lines[line_number+1][0][0].y1: # between current and next line
                        for i in range(len(line) + 1):  # i means between (i-1)th and ith text frag.
                            if i == 0:
                                if var_frag_x1 <= line[i][0].x0:
                                    position = (line_number, i)
                                    break
                            elif i == len(line):
                                if var_frag_x0 >= line[i-1][-1].x1:
                                    position = (line_number, i)
                                    break
                            else:
                                if line[i-1][-1].x1 <= var_frag_x0 and var_frag_x1 <= line[i][0].x0:
                                    position = (line_number, i)
                                    break
                    if position:
                        break  # breaking the loop for lines
            if not position:
                position = (len(lines), 0)  # maybe some variable in wrong cls block
            if isinstance(var_frag, list):
                result[position].extend(var_frag)
            else:
                result[position].append(var_frag)

        # ok, now we find a position for every var frag.
        string_content = ""
        for line_number, line in enumerate(lines):
            for i in range(len(line)+1):
                if (line_number, i) in result:
                    items = result[(line_number, i)]
                    chars = sorted([item for item in items if isinstance(item, LTChar)], key=lambda x: x.x0)
                    self.var.append(chars)
                    self.varl.append([item for item in items if not isinstance(item, LTChar)]) # non list is LTLine or LTRect
                    self.varf.append(chars[0].y0 - line[0][0].y0)
                    string_content += f" {{v{next_var}}}"
                    next_var += 1
                if i < len(line):
                    if string_content:
                        string_content += " "
                    for j in range(len(line[i])):
                        if j > 0 and line[i][j].x0 > line[i][j-1].x1 + 1:  # missing space.
                            string_content += " "
                        string_content += line[i][j].get_text()
        self.sstk.append(string_content)
        child = self.lt_chars[0]
        self.pstk.append(
            Paragraph(child.y0, child.x0,
                      min([c.x0 for c in self.lt_chars]), max([c.x1 for c in self.lt_chars]),
                      min([c.y0 for c in self.lt_chars]), max([c.y1 for c in self.lt_chars]),
                      fontname, size, len(lines) > 1))

        if (len(lines), 0) in result:
            # Some var frags are not placed in the text. 
            # We'll treat them as a new paragraph, use original absolute position to print them.
            self.sstk.append(f"{{v{next_var}}}")
            next_var += 1
            items = result[(len(lines), 0)]
            child = items[0]
            self.pstk.append(Paragraph(child.y0, child.x0,
                      min([c.x0 for c in items]), max([c.x1 for c in items]),
                      min([c.y0 for c in items]), max([c.y1 for c in items]),
                      fontname, 0, False))
            self.var.append([item for item in items if isinstance(item, LTChar)])
            self.varl.append([item for item in items if not isinstance(item, LTChar)])
            self.varf.append(0)
    
    @staticmethod
    def preprocess(clscontent_dict: Dict[int, 'CLSContent']) -> list['CLSContent']:
        '''
        yolo layout may split a paragraph into two, due to some fomula higher than line height.
        we want to merge them back into one.
        '''
        if len(clscontent_dict) == 0:
            return []
        # sort by y0
        content_list = sorted(clscontent_dict.values(), key=lambda x: x.y0, reverse=True)
        result = []
        current = content_list[0]
        for i in range(1, len(content_list)):
            next_clscontent = content_list[i]
            possible_tall_fomular = next_clscontent.y1 > next_clscontent.lt_chars[0].y1
            if possible_tall_fomular and (
                abs(current.x0 - next_clscontent.x0) < MAGIC and
                abs(current.x1 - next_clscontent.x1) < MAGIC and
                abs(current.y0 - next_clscontent.y1) < MAGIC):
                current.lt_chars.extend(next_clscontent.lt_chars)
                current.lt_lines.extend(next_clscontent.lt_lines)
                current.finish_add()
            else:
                result.append(current)
                current = next_clscontent
        result.append(current)
        return result

# fmt: off
class TranslateConverter2(PDFConverterEx):
    def __init__(
        self,
        rsrcmgr,
        vfont: str = None,
        vchar: str = None,
        thread: int = 0,
        layout={},
        lang_in: str = "",
        lang_out: str = "",
        service: str = "",
        noto_name: str = "",
        noto: Font = None,
        noto_bold_name: str = "",
        noto_bold: Font = None,
        envs: Dict = None,
        prompt: Template = None,
    ) -> None:
        super().__init__(rsrcmgr)
        self.vfont = vfont
        self.vchar = vchar
        self.thread = thread
        self.layout = layout
        self.noto_name = noto_name
        self.noto = noto
        self.noto_bold_name = noto_bold_name
        self.noto_bold = noto_bold
        self.translator: BaseTranslator = None
        param = service.split(":", 1)
        service_name = param[0]
        service_model = param[1] if len(param) > 1 else None
        if not envs:
            envs = {}
        for translator in [GoogleTranslator, BingTranslator, DeepLTranslator, DeepLXTranslator, OllamaTranslator, XinferenceTranslator, AzureOpenAITranslator,
                           OpenAITranslator, ZhipuTranslator, ModelScopeTranslator, SiliconTranslator, GeminiTranslator, AzureTranslator, TencentTranslator, DifyTranslator, AnythingLLMTranslator, ArgosTranslator, GorkTranslator, GroqTranslator, DeepseekTranslator, OpenAIlikedTranslator, QwenMtTranslator,]:
            if service_name == translator.name:
                self.translator = translator(lang_in, lang_out, service_model, envs=envs, prompt=prompt)
        if not self.translator:
            raise ValueError("Unsupported translation service")

    def receive_layout(self, ltpage: LTPage):
        # 段落
        sstk: list[str] = []            # 段落文字栈
        pstk: list[Paragraph] = []      # 段落属性栈
        vbkt: int = 0                   # 段落公式括号计数
        # 公式组
        vstk: list[LTChar] = []         # 公式符号组
        vlstk: list[LTLine] = []        # 公式线条组
        vfix: float = 0                 # 公式纵向偏移
        # 公式组栈
        var: list[list[LTChar]] = []    # 公式符号组栈
        varl: list[list[LTLine]] = []   # 公式线条组栈
        varf: list[float] = []          # 公式纵向偏移栈
        vlen: list[float] = []          # 公式宽度栈
        # 全局
        lstk: list[LTLine] = []         # 全局线条栈
        xt: LTChar = None               # 上一个字符
        xt_cls: int = -1                # 上一个字符所属段落，保证无论第一个字符属于哪个类别都可以触发新段落
        vmax: float = ltpage.width / 4  # 行内公式最大宽度
        ops: str = ""                   # 渲染结果

        # ############################################################
        # # A. 原文档解析
        clscontent_dict = {}
        global_var = []
        for child in ltpage:
            layout = self.layout[ltpage.pageid]
            # ltpage.height 可能是 fig 里面的高度，这里统一用 layout.shape
            h, w = layout.shape
            # 读取当前字符在 layout 中的类别
            cx, cy = np.clip(int(child.x0), 0, w - 1), np.clip(int(child.y0), 0, h - 1)
            cls = layout[cy, cx]
            if (isinstance(child, LTChar) or isinstance(child, LTLine) or isinstance(child, LTRect)):
                if cls > 1:
                    if cls not in clscontent_dict:
                        clscontent_dict[cls] = CLSContent(ltpage)
                    if isinstance(child, LTChar):
                        clscontent_dict[cls].add_char(child)
                    else:
                        clscontent_dict[cls].add_line(child)
                else:
                    if isinstance(child, LTChar):
                        global_var.append(child)
                    else:
                        lstk.append(child)
        for _, clscontent in clscontent_dict.items():
            clscontent.finish_add()
        clscontent_list = CLSContent.preprocess(clscontent_dict)
        next_var = 0
        for clscontent in clscontent_list:
            clscontent.process(next_var)
            sstk.extend(clscontent.sstk)
            pstk.extend(clscontent.pstk)
            var.extend(clscontent.var)
            varl.extend(clscontent.varl)
            varf.extend(clscontent.varf)
            next_var = len(var)
        if global_var:
            sstk.append(f"{{v{next_var}}}")
            child = global_var[0]
            pstk.append(Paragraph(child.y0, child.x0,
                      min([c.x0 for c in global_var]), max([c.x1 for c in global_var]),
                      min([c.y0 for c in global_var]), max([c.y1 for c in global_var]),
                      "", child.size, False))
            var.append(global_var)
            varl.append([])
            varf.append(0)
        
        log.debug("\n==========[VSTACK]==========\n")
        for id, v in enumerate(var):  # 计算公式宽度
            l = max([vch.x1 for vch in v]) - min([vch.x0 for vch in v])
            log.debug(f'< {l:.1f} {v[0].x0:.1f} {v[0].y0:.1f} {v[0].cid} {v[0].fontname} {len(varl[id])} > v{id} = {"".join([ch.get_text() for ch in v])}')
            vlen.append(l)

        ############################################################
        # B. 段落翻译
        log.debug("\n==========[SSTACK]==========\n")

        @retry(wait=wait_fixed(1))
        def worker(s: str):  # 多线程翻译
            if not s.strip() or re.match(r"^\{v\d+\}$", s):  # 空白和公式不翻译
                return s
            try:
                new = self.translator.translate(s)
                return new
            except BaseException as e:
                if log.isEnabledFor(logging.DEBUG):
                    log.exception(e)
                else:
                    log.exception(e, exc_info=False)
                raise e
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.thread
        ) as executor:
            news = list(executor.map(worker, sstk))

        ############################################################
        # C. 新文档排版
        def raw_string(fcur: str, cstk: str):  # 编码字符串
            if fcur == self.noto_name or fcur == self.noto_bold_name:
                return "".join(["%04x" % self.noto.has_glyph(ord(c)) for c in cstk])
            elif isinstance(self.fontmap[fcur], PDFCIDFont):  # 判断编码长度
                return "".join(["%04x" % ord(c) for c in cstk])
            else:
                return "".join(["%02x" % ord(c) for c in cstk])

        # 根据目标语言获取默认行距
        LANG_LINEHEIGHT_MAP = {
            "zh-cn": 1.4, "zh-tw": 1.4, "zh-hans": 1.4, "zh-hant": 1.4, "zh": 1.4,
            "ja": 1.1, "ko": 1.2, "en": 1.2, "ar": 1.0, "ru": 0.8, "uk": 0.8, "ta": 0.8
        }
        default_line_height = LANG_LINEHEIGHT_MAP.get(self.translator.lang_out.lower(), 1.1) # 小语种默认1.1
        _x, _y = 0, 0
        ops_list = []

        def gen_op_txt(font, size, x, y, rtxt):
            return f"/{font} {size:f} Tf 1 0 0 1 {x:f} {y:f} Tm [<{rtxt}>] TJ "

        def gen_op_line(x, y, xlen, ylen, linewidth):
            return f"ET q 1 0 0 1 {x:f} {y:f} cm [] 0 d 0 J {linewidth:f} w 0 0 m {xlen:f} {ylen:f} l S Q BT "

        for id, new in enumerate(news):
            x: float = pstk[id].x                       # 段落初始横坐标
            y: float = pstk[id].y                       # 段落初始纵坐标
            x0: float = pstk[id].x0                     # 段落左边界
            x1: float = pstk[id].x1                     # 段落右边界
            height: float = pstk[id].y1 - pstk[id].y0   # 段落高度
            size: float = pstk[id].size                 # 段落字体大小
            brk: bool = pstk[id].brk                    # 段落换行标记
            cstk: str = ""                              # 当前文字栈
            fcur: str = None                            # 当前字体 ID
            lidx = 0                                    # 记录换行次数
            tx = x
            fcur_ = fcur
            ptr = 0
            log.debug(f"< {y} {x} {x0} {x1} {size} {brk} > {sstk[id]} | {new}")
            is_bold = "bold" in pstk[id].fontname.lower()

            ops_vals: list[dict] = []

            while ptr < len(new):
                vy_regex = re.match(
                    r"\{\s*v([\d\s]+)\}", new[ptr:], re.IGNORECASE
                )  # 匹配 {vn} 公式标记
                mod = 0  # 文字修饰符
                if vy_regex:  # 加载公式
                    ptr += len(vy_regex.group(0))
                    try:
                        vid = int(vy_regex.group(1).replace(" ", ""))
                        adv = vlen[vid]
                    except Exception:
                        continue  # 翻译器可能会自动补个越界的公式标记
                    if var[vid][-1].get_text() and unicodedata.category(var[vid][-1].get_text()[0]) in ["Lm", "Mn", "Sk"]:  # 文字修饰符
                        mod = var[vid][-1].width
                else:  # 加载文字
                    ch = new[ptr]
                    fcur_ = None
                    try:
                        if fcur_ is None and self.fontmap["tiro"].to_unichr(ord(ch)) == ch:
                            fcur_ = "tiro"  # 默认拉丁字体
                    except Exception:
                        pass
                    if fcur_ is None:
                        fcur_ = self.noto_bold_name if is_bold else self.noto_name
                    if fcur_ == self.noto_name: # FIXME: change to CONST
                        adv = self.noto.char_lengths(ch, size)[0]
                    elif fcur_ == self.noto_bold_name:
                        adv = self.noto_bold.char_lengths(ch, size)[0]
                    else:
                        adv = self.fontmap[fcur_].char_width(ord(ch)) * size
                    ptr += 1
                if (                                # 输出文字缓冲区
                    fcur_ != fcur                   # 1. 字体更新
                    or vy_regex                     # 2. 插入公式
                    or x + adv > x1 + 0.1 * size    # 3. 到达右边界（可能一整行都被符号化，这里需要考虑浮点误差）
                ):
                    if cstk:
                        ops_vals.append({
                            "type": OpType.TEXT,
                            "font": fcur,
                            "size": size,
                            "x": tx,
                            "dy": 0,
                            "rtxt": raw_string(fcur, cstk),
                            "lidx": lidx
                        })
                        cstk = ""
                if brk and x + adv > x1 + 0.1 * size:  # 到达右边界且原文段落存在换行
                    x = x0
                    lidx += 1
                if vy_regex:  # 插入公式
                    fix = 0
                    if fcur is not None:  # 段落内公式修正纵向偏移
                        fix = varf[vid]
                    for vch in var[vid]:  # 排版公式字符
                        vc = chr(vch.cid)
                        ops_vals.append({
                            "type": OpType.TEXT,
                            "font": self.fontid[vch.font],
                            "size": vch.size,
                            "x": x + vch.x0 - var[vid][0].x0,
                            "dy": fix + vch.y0 - var[vid][0].y0,
                            "rtxt": raw_string(self.fontid[vch.font], vc),
                            "lidx": lidx
                        })
                        if log.isEnabledFor(logging.DEBUG):
                            lstk.append(LTLine(0.1, (_x, _y), (x + vch.x0 - var[vid][0].x0, fix + y + vch.y0 - var[vid][0].y0)))
                            _x, _y = x + vch.x0 - var[vid][0].x0, fix + y + vch.y0 - var[vid][0].y0
                    for l in varl[vid]:  # 排版公式线条
                        if isinstance(l, LTLine):
                            if l.linewidth < 5:  # hack 有的文档会用粗线条当图片背景
                                ops_vals.append({
                                    "type": OpType.LINE,
                                    "x": l.pts[0][0] + x - var[vid][0].x0,
                                    "dy": l.pts[0][1] + fix - var[vid][0].y0,
                                    "linewidth": l.linewidth,
                                    "xlen": l.pts[1][0] - l.pts[0][0],
                                    "ylen": l.pts[1][1] - l.pts[0][1],
                                    "lidx": lidx
                                })
                            elif isinstance(l, LTRect):
                                x0, y0, x1, y1 = l.x0, l.y0, l.x1, l.y1
            
                                # 生成矩形的四条边
                                rect_lines = [
                                    ((x0, y0), (x1, y0)),  # 底边
                                    ((x1, y0), (x1, y1)),  # 右边
                                    ((x1, y1), (x0, y1)),  # 顶边
                                    ((x0, y1), (x0, y0))   # 左边
                                ]
                                
                                # 遍历矩形的四条边，并存入 ops_vals
                                for (p1, p2) in rect_lines:
                                    ops_vals.append({
                                        "type": OpType.LINE,
                                        "x": p1[0] + x - var[vid][0].x0,
                                        "dy": p1[1] + fix - var[vid][0].y0,
                                        "linewidth": l.linewidth,
                                        "xlen": p2[0] - p1[0],
                                        "ylen": p2[1] - p1[1],
                                        "lidx": lidx
                                    })
                else:  # 插入文字缓冲区
                    if not cstk:  # 单行开头
                        tx = x
                        if x == x0 and ch == " ":  # 消除段落换行空格
                            adv = 0
                        else:
                            cstk += ch
                    else:
                        cstk += ch
                adv -= mod # 文字修饰符
                fcur = fcur_
                x += adv
                if log.isEnabledFor(logging.DEBUG):
                    lstk.append(LTLine(0.1, (_x, _y), (x, y)))
                    _x, _y = x, y
            # 处理结尾
            if cstk:
                ops_vals.append({
                    "type": OpType.TEXT,
                    "font": fcur,
                    "size": size,
                    "x": tx,
                    "dy": 0,
                    "rtxt": raw_string(fcur, cstk),
                    "lidx": lidx
                })

            line_height = default_line_height

            while (lidx + 1) * size * line_height > height and line_height >= 1:
                line_height -= 0.05

            for vals in ops_vals:
                if vals["type"] == OpType.TEXT:
                    ops_list.append(gen_op_txt(vals["font"], vals["size"], vals["x"], vals["dy"] + y - vals["lidx"] * size * line_height, vals["rtxt"]))
                elif vals["type"] == OpType.LINE:
                    ops_list.append(gen_op_line(vals["x"], vals["dy"] + y - vals["lidx"] * size * line_height, vals["xlen"], vals["ylen"], vals["linewidth"]))

        for l in lstk:  # 排版全局线条
            if l.linewidth < 5:  # hack 有的文档会用粗线条当图片背景
                ops_list.append(gen_op_line(l.pts[0][0], l.pts[0][1], l.pts[1][0] - l.pts[0][0], l.pts[1][1] - l.pts[0][1], l.linewidth))

        ops = f"BT {''.join(ops_list)}ET "
        return ops


class OpType(Enum):
    TEXT = "text"
    LINE = "line"
