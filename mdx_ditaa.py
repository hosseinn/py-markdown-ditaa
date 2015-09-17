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
import shutil
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


class DitaaPreprocessor(Preprocessor):

    def __init__(self, *args, **config):
        self.config = config

    def generate_image_path(self, plaintext):
        """
        Return an image path based on a hash of the plaintext input.
        """
        adler32 = ctypes.c_uint32(zlib.adler32(b(plaintext))).value
        img_basename = "diagram-%x.png" % adler32
        image_path = os.path.join(self.config['ditaa_image_dir'], img_basename)
        return image_path

    def generate_diagram(self, plaintext):
        """
        Run ditaa with plaintext input.
        Return relative path to the generated image.
        """
        img_dest = self.generate_image_path(plaintext)
        src_fd, src_fname = tempfile.mkstemp(prefix="ditaasrc", text=True)
        out_fd, out_fname = tempfile.mkstemp(prefix="ditaaout", text=True)
        with os.fdopen(src_fd, "w") as src:
           src.write(plaintext)
        try:
            ditaa_cmd = self.config['ditaa_cmd']
            cmd = ditaa_cmd.format(infile=src_fname, outfile=img_dest)
            with os.fdopen(out_fd, "w") as out:
                retval = subprocess.check_call(cmd.split(), stdout=out)

            if self.config.get('extra_copy_path', None):
                try:
                    shutil.copy(img_dest, self.config['extra_copy_path'])
                except:
                    pass
            return os.path.relpath(img_dest, os.getcwd())

        except Exception as e:
            return None
        finally:
            os.unlink(src_fname)
            os.unlink(out_fname)

    def run(self, lines):
        START_TAG = "```ditaa"
        END_TAG = "```"
        new_lines = []
        ditaa_prefix = ""
        ditaa_lines = []
        in_diagram = False
        path_override = None
        for ln in lines:
            if in_diagram:  # lines of a diagram
                if ln == ditaa_prefix + END_TAG:
                    # strip line prefix if any (whitespace, bird marks)
                    plen = len(ditaa_prefix)
                    ditaa_lines = [dln[plen:] for dln in ditaa_lines]
                    ditaa_code = "\n".join(ditaa_lines)
                    filename = self.generate_diagram(ditaa_code)
                    if filename:
                        if path_override:
                            mkdocs_path = os.path.join(path_override, os.path.basename(filename))
                        else:
                            mkdocs_path = os.path.join(self.config['extra_copy_path'], os.path.basename(filename))
                        new_lines.append(ditaa_prefix + "![%s](%s)" % (mkdocs_path, mkdocs_path))
                        path_override = None
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
                postfix = ln[start + len(START_TAG) + 1:] if start >= 0 else ""
                if postfix and postfix.startswith('path='):
                    path_override = postfix[5:]
                    ln = ln[:-len(postfix) - 1]

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
        extra_copy_path = kwargs.get('extra_copy_path', None)

        if 'DITAA_CMD' in os.environ:
            ditaa_cmd = os.environ.get("DITAA_CMD")
        if 'DITAA_IMAGE_DIR' in os.environ:
            ditaa_image_dir = os.environ.get("DITAA_IMAGE_DIR")

        self.config = {
            'ditaa_cmd': [ditaa_cmd,
                "Full command line to launch ditaa. Defaults to:"
                "{}".format(ditaa_cmd)],
            'ditaa_image_dir': [ditaa_image_dir,
                "Full path to directory where images will be saved."],
            'extra_copy_path': [extra_copy_path,
                "Set this path to save an extra copy into "
                "the specified directory."]
        }

        super(DitaaExtension, self).__init__(**kwargs)

    def extendMarkdown(self, md, md_globals):
        ditaa_ext = self.PreprocessorClass(md, self.config)
        ditaa_ext.config = self.getConfigs()

        md.registerExtension(self)
        location = "<fenced_code" if ("fenced_code" in md.preprocessors) else "_begin"
        md.preprocessors.add("ditaa", ditaa_ext, location)


def makeExtension(**kwargs):
    return DitaaExtension(**kwargs)
