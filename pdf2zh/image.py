import os
import os.path
import struct
from io import BytesIO
from typing import BinaryIO, Tuple

try:
    from typing import Literal
except ImportError:
    # Literal was introduced in Python 3.8
    from typing_extensions import Literal  # type: ignore[assignment]

from pdf2zh.jbig2 import JBIG2StreamReader, JBIG2StreamWriter
from pdf2zh.layout import LTImage
from pdf2zh.pdfcolor import (
    LITERAL_DEVICE_CMYK,
    LITERAL_DEVICE_GRAY,
    LITERAL_DEVICE_RGB,
    LITERAL_INLINE_DEVICE_GRAY,
    LITERAL_INLINE_DEVICE_RGB,
)
from pdf2zh.pdfexceptions import PDFValueError
from pdf2zh.pdftypes import (
    LITERALS_DCT_DECODE,
    LITERALS_FLATE_DECODE,
    LITERALS_JBIG2_DECODE,
    LITERALS_JPX_DECODE,
)

PIL_ERROR_MESSAGE = (
    "Could not import Pillow. This dependency of pdf2zh.six is not "
    "installed by default. You need it to to save jpg images to a file. Install it "
    "with `pip install 'pdf2zh.six[image]'`"
)


def align32(x: int) -> int:
    return ((x + 3) // 4) * 4


class BMPWriter:
    def __init__(self, fp: BinaryIO, bits: int, width: int, height: int) -> None:
        self.fp = fp
        self.bits = bits
        self.width = width
        self.height = height
        if bits == 1:
            ncols = 2
        elif bits == 8:
            ncols = 256
        elif bits == 24:
            ncols = 0
        else:
            raise PDFValueError(bits)
        self.linesize = align32((self.width * self.bits + 7) // 8)
        self.datasize = self.linesize * self.height
        headersize = 14 + 40 + ncols * 4
        info = struct.pack(
            "<IiiHHIIIIII",
            40,
            self.width,
            self.height,
            1,
            self.bits,
            0,
            self.datasize,
            0,
            0,
            ncols,
            0,
        )
        assert len(info) == 40, str(len(info))
        header = struct.pack(
            "<ccIHHI",
            b"B",
            b"M",
            headersize + self.datasize,
            0,
            0,
            headersize,
        )
        assert len(header) == 14, str(len(header))
        self.fp.write(header)
        self.fp.write(info)
        if ncols == 2:
            # B&W color table
            for i in (0, 255):
                self.fp.write(struct.pack("BBBx", i, i, i))
        elif ncols == 256:
            # grayscale color table
            for i in range(256):
                self.fp.write(struct.pack("BBBx", i, i, i))
        self.pos0 = self.fp.tell()
        self.pos1 = self.pos0 + self.datasize

    def write_line(self, y: int, data: bytes) -> None:
        self.fp.seek(self.pos1 - (y + 1) * self.linesize)
        self.fp.write(data)


class ImageWriter:
    """Write image to a file

    Supports various image types: JPEG, JBIG2 and bitmaps
    """

    def __init__(self, outdir: str) -> None:
        self.outdir = outdir
        if not os.path.exists(self.outdir):
            os.makedirs(self.outdir)

    def export_image(self, image: LTImage) -> str:
        """Save an LTImage to disk"""
        (width, height) = image.srcsize

        filters = image.stream.get_filters()

        if filters[-1][0] in LITERALS_DCT_DECODE:
            name = self._save_jpeg(image)

        elif filters[-1][0] in LITERALS_JPX_DECODE:
            name = self._save_jpeg2000(image)

        elif self._is_jbig2_iamge(image):
            name = self._save_jbig2(image)

        elif image.bits == 1:
            name = self._save_bmp(image, width, height, (width + 7) // 8, image.bits)

        elif image.bits == 8 and (
            LITERAL_DEVICE_RGB in image.colorspace
            or LITERAL_INLINE_DEVICE_RGB in image.colorspace
        ):
            name = self._save_bmp(image, width, height, width * 3, image.bits * 3)

        elif image.bits == 8 and (
            LITERAL_DEVICE_GRAY in image.colorspace
            or LITERAL_INLINE_DEVICE_GRAY in image.colorspace
        ):
            name = self._save_bmp(image, width, height, width, image.bits)

        elif len(filters) == 1 and filters[0][0] in LITERALS_FLATE_DECODE:
            name = self._save_bytes(image)

        else:
            name = self._save_raw(image)

        return name

    def _save_jpeg(self, image: LTImage) -> str:
        """Save a JPEG encoded image"""
        data = image.stream.get_data()

        name, path = self._create_unique_image_name(image, ".jpg")
        with open(path, "wb") as fp:
            if LITERAL_DEVICE_CMYK in image.colorspace:
                try:
                    from PIL import Image, ImageChops  # type: ignore[import]
                except ImportError:
                    raise ImportError(PIL_ERROR_MESSAGE)

                ifp = BytesIO(data)
                i = Image.open(ifp)
                i = ImageChops.invert(i)
                i = i.convert("RGB")
                i.save(fp, "JPEG")
            else:
                fp.write(data)

        return name

    def _save_jpeg2000(self, image: LTImage) -> str:
        """Save a JPEG 2000 encoded image"""
        data = image.stream.get_data()

        name, path = self._create_unique_image_name(image, ".jp2")
        with open(path, "wb") as fp:
            try:
                from PIL import Image  # type: ignore[import]
            except ImportError:
                raise ImportError(PIL_ERROR_MESSAGE)

            # if we just write the raw data, most image programs
            # that I have tried cannot open the file. However,
            # open and saving with PIL produces a file that
            # seems to be easily opened by other programs
            ifp = BytesIO(data)
            i = Image.open(ifp)
            i.save(fp, "JPEG2000")
        return name

    def _save_jbig2(self, image: LTImage) -> str:
        """Save a JBIG2 encoded image"""
        name, path = self._create_unique_image_name(image, ".jb2")
        with open(path, "wb") as fp:
            input_stream = BytesIO()

            global_streams = []
            filters = image.stream.get_filters()
            for filter_name, params in filters:
                if filter_name in LITERALS_JBIG2_DECODE:
                    global_streams.append(params["JBIG2Globals"].resolve())

            if len(global_streams) > 1:
                msg = (
                    "There should never be more than one JBIG2Globals "
                    "associated with a JBIG2 embedded image"
                )
                raise PDFValueError(msg)
            if len(global_streams) == 1:
                input_stream.write(global_streams[0].get_data().rstrip(b"\n"))
            input_stream.write(image.stream.get_data())
            input_stream.seek(0)
            reader = JBIG2StreamReader(input_stream)
            segments = reader.get_segments()

            writer = JBIG2StreamWriter(fp)
            writer.write_file(segments)
        return name

    def _save_bmp(
        self,
        image: LTImage,
        width: int,
        height: int,
        bytes_per_line: int,
        bits: int,
    ) -> str:
        """Save a BMP encoded image"""
        name, path = self._create_unique_image_name(image, ".bmp")
        with open(path, "wb") as fp:
            bmp = BMPWriter(fp, bits, width, height)
            data = image.stream.get_data()
            i = 0
            for y in range(height):
                bmp.write_line(y, data[i : i + bytes_per_line])
                i += bytes_per_line
        return name

    def _save_bytes(self, image: LTImage) -> str:
        """Save an image without encoding, just bytes"""
        name, path = self._create_unique_image_name(image, ".jpg")
        width, height = image.srcsize
        channels = len(image.stream.get_data()) / width / height / (image.bits / 8)
        with open(path, "wb") as fp:
            try:
                from PIL import (
                    Image,  # type: ignore[import]
                    ImageOps,
                )
            except ImportError:
                raise ImportError(PIL_ERROR_MESSAGE)

            mode: Literal["1", "L", "RGB", "CMYK"]
            if image.bits == 1:
                mode = "1"
            elif image.bits == 8 and channels == 1:
                mode = "L"
            elif image.bits == 8 and channels == 3:
                mode = "RGB"
            elif image.bits == 8 and channels == 4:
                mode = "CMYK"

            img = Image.frombytes(mode, image.srcsize, image.stream.get_data(), "raw")
            if mode == "L":
                img = ImageOps.invert(img)

            img.save(fp)

        return name

    def _save_raw(self, image: LTImage) -> str:
        """Save an image with unknown encoding"""
        ext = ".%d.%dx%d.img" % (image.bits, image.srcsize[0], image.srcsize[1])
        name, path = self._create_unique_image_name(image, ext)

        with open(path, "wb") as fp:
            fp.write(image.stream.get_data())
        return name

    @staticmethod
    def _is_jbig2_iamge(image: LTImage) -> bool:
        filters = image.stream.get_filters()
        for filter_name, params in filters:
            if filter_name in LITERALS_JBIG2_DECODE:
                return True
        return False

    def _create_unique_image_name(self, image: LTImage, ext: str) -> Tuple[str, str]:
        name = image.name + ext
        path = os.path.join(self.outdir, name)
        img_index = 0
        while os.path.exists(path):
            name = "%s.%d%s" % (image.name, img_index, ext)
            path = os.path.join(self.outdir, name)
            img_index += 1
        return name, path
