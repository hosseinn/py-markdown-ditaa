"""
A Python Markdown extension to convert plain-text diagrams to images.
"""

# The MIT License (MIT)
#
# Copyright (c) 2014 Sergey Astanin
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.


import ctypes
import os
import platform
import subprocess
import tempfile
import zlib

from markdown.preprocessors import Preprocessor
from markdown.extensions import Extension


if platform.python_version_tuple() >= ('3', '0', '0'):
    def b(string):
        return bytes(string, "UTF-8")
else:
    def b(string):
        return string


def generate_image_path(plaintext, image_dir):
    adler32 = ctypes.c_uint32(zlib.adler32(b(plaintext))).value
    img_basename = "diagram-%x.png" % adler32
    image_path = os.path.join(image_dir, img_basename)
    return image_path


def generate_diagram(plaintext, cmd_path, image_dir):
    """Run ditaa with plaintext input.
    Return relative path to the generated image.
    """

    img_path = generate_image_path(plaintext, image_dir)
    src_fd, src_fname = tempfile.mkstemp(prefix="ditaasrc", text=True)
    out_fd, out_fname = tempfile.mkstemp(prefix="ditaaout", text=True)
    with os.fdopen(src_fd, "w") as src:
       src.write(plaintext)
    try:
        cmd = cmd_path.format(infile=src_fname, outfile=img_path).split()
        with os.fdopen(out_fd, "w") as out:
            retval = subprocess.check_call(cmd, stdout=out)
        return os.path.relpath(img_path, os.getcwd())
    except:
        return None
    finally:
        os.unlink(src_fname)
        os.unlink(out_fname)


class DitaaPreprocessor(Preprocessor):

    def __init__(self, *args, **config):
        self.config = config

    def run(self, lines):
        START_TAG = "```ditaa"
        END_TAG = "```"
        new_lines = []
        ditaa_prefix = ""
        ditaa_lines = []
        in_diagram = False
        for ln in lines:
            if in_diagram:  # lines of a diagram
                if ln == ditaa_prefix + END_TAG:
                    # strip line prefix if any (whitespace, bird marks)
                    plen = len(ditaa_prefix)
                    ditaa_lines = [dln[plen:] for dln in ditaa_lines]
                    ditaa_code = "\n".join(ditaa_lines)
                    filename = generate_diagram(ditaa_code, self.config['ditaa_cmd'], self.config['ditaa_image_dir'])
                    if filename:
                        new_lines.append(ditaa_prefix + "![%s](%s)" % (filename, filename))
                    else:
                        md_code = [ditaa_prefix + "    " + dln for dln in ditaa_lines]
                        new_lines.extend([""] + md_code + [""])
                    in_diagram = False
                    ditaa_lines = []
                else:
                    ditaa_lines.append(ln)
            else:  # normal lines
                start = ln.find(START_TAG)
                prefix = ln[:start] if start >= 0 else ""
                # code block may be nested within a list item or a blockquote
                if start >= 0 and ln.endswith(START_TAG) and not prefix.strip(" \t>"):
                    in_diagram = True
                    ditaa_prefix = prefix
                else:
                    new_lines.append(ln)
        return new_lines


class DitaaExtension(Extension):

    PreprocessorClass = DitaaPreprocessor

    def __init__(self, **kwargs):
        ditaa_cmd = kwargs.get('ditaa_cmd', 'ditaa {infile} {outfile} --overwrite')
        ditaa_image_dir = kwargs.get('ditaa_image_dir', '.')

        if 'DITAA_CMD' in os.environ:
            ditaa_cmd = os.environ.get("DITAA_CMD")
        if 'DITAA_IMAGE_DIR' in os.environ:
            ditaa_image_dir = os.environ.get("DITAA_IMAGE_DIR")

        self.config = {
            'ditaa_cmd': [ditaa_cmd,
                "Full command line to launch ditaa. Defaults to:"
                "{}".format(ditaa_cmd)],
            'ditaa_image_dir': [ditaa_image_dir,
                "Full path to directory where images will be saved."]
        }

        super(DitaaExtension, self).__init__(**kwargs)

    def extendMarkdown(self, md, md_globals):
        ditaa_ext = self.PreprocessorClass(md, self.config)
        ditaa_ext.config = self.getConfigs()

        #md.registerExtension(self)
        location = "<fenced_code" if ("fenced_code" in md.preprocessors) else "_begin"
        md.preprocessors.add("ditaa", ditaa_ext, location)


def makeExtension(**kwargs):
    return DitaaExtension(**kwargs)
