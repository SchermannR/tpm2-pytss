import os
import ast
import stat
import glob
import shlex
import shutil
from io import open
from subprocess import check_output
from setuptools.command.build_ext import build_ext
from setuptools import find_packages, setup, Extension

ORG = "tpm2-software"
NAME = "tpm2-pytss"
DESCRIPTION = "TPM 2.0 TSS Bindings for Python"
AUTHOR_NAME = "John Andersen"
AUTHOR_EMAIL = "john.s.andersen@intel.com"
INSTALL_REQUIRES = []

IMPORT_NAME = NAME.replace("-", "_")

SELF_PATH = os.path.dirname(os.path.realpath(__file__))

with open(os.path.join(SELF_PATH, IMPORT_NAME, "version.py"), "r") as f:
    for line in f:
        if line.startswith("VERSION"):
            VERSION = ast.literal_eval(line.strip().split("=")[-1].strip())
            break

with open(os.path.join(SELF_PATH, "README.md"), "r", encoding="utf-8") as f:
    readme = f.read()


class PkgConfigNeededExtension(Extension):
    """
    By creating a subclass of Extension and using the :py:func:property builtin
    we can make it so that pkg-config doesn't get called unless the user
    attempts to build from source. Otherwise we'd run into issues installing the
    built binary on systems that don't have pkg-config.
    """

    def __init__(self, *args, pkg_config_cflags=None, pkg_config_libs=None, **kwargs):
        # Default to empty array if not given
        if pkg_config_cflags is None:
            pkg_config_cflags = []
        if pkg_config_libs is None:
            pkg_config_libs = []
        self.pkg_config_cflags = pkg_config_cflags
        self.pkg_config_libs = pkg_config_libs
        # Will be populated by respective non-underscore setters
        self._libraries = []
        self._include_dirs = []
        self._swig_opts = []
        super().__init__(*args, **kwargs)

    @property
    def cc_include_dirs(self):
        if not self.pkg_config_cflags:
            return []
        return shlex.split(
            check_output(["pkg-config", "--cflags"] + self.pkg_config_cflags,
                env=dict(os.environ, PKG_CONFIG_ALLOW_SYSTEM_CFLAGS="1")).decode()
        )

    @property
    def cc_libraries(self):
        if not self.pkg_config_libs:
            return []
        return shlex.split(
            check_output(["pkg-config", "--libs"] + self.pkg_config_libs).decode()
        )

    def _strip_leading(self, number, iterable):
        """
        Strips number characters from the begining of each string in iterable.
        """
        return list(map(lambda string: string[number:], iterable))

    @property
    def include_dirs(self):
        return self._strip_leading(2, self.cc_include_dirs) + self._include_dirs

    @include_dirs.setter
    def include_dirs(self, value):
        self._include_dirs = value

    @property
    def libraries(self):
        return self._strip_leading(2, self.cc_libraries) + self._libraries

    @libraries.setter
    def libraries(self, value):
        self._libraries = value

    @property
    def swig_opts(self):
        return (
            list(filter(lambda option: option.startswith("-I"), self.cc_include_dirs))
            + self._swig_opts
        )

    @swig_opts.setter
    def swig_opts(self, value):
        self._swig_opts = value


class BuildExtThenCopySWIGPy(build_ext):
    def run(self):
        super().run()
        # This is needed because test copies the binding files into IMPORT_NAME
        # but build does not. Making this necessary for working with the package
        # installed in development mode.
        for src in glob.glob(
            os.path.join(SELF_PATH, "build", "lib.*", "**", "*.so"), recursive=True
        ):
            dst = os.path.join(SELF_PATH, IMPORT_NAME, os.path.basename(src))
            print("{} -> {}".format(src, dst))
            shutil.copyfile(src, dst)
            os.chmod(
                dst,
                stat.S_IRUSR
                | stat.S_IWUSR
                | stat.S_IXUSR
                | stat.S_IRGRP
                | stat.S_IXGRP
                | stat.S_IROTH
                | stat.S_IXOTH,
            )


setup(
    name=NAME,
    version=VERSION,
    description=DESCRIPTION,
    long_description=readme,
    long_description_content_type="text/markdown",
    author=AUTHOR_NAME,
    author_email=AUTHOR_EMAIL,
    maintainer=AUTHOR_NAME,
    maintainer_email=AUTHOR_EMAIL,
    url="https://github.com/{}/{}".format(ORG, NAME),
    license="MIT",
    keywords=["tpm2", "security"],
    classifiers=[
        "Development Status :: 1 - Planning",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: Implementation :: CPython",
    ],
    install_requires=INSTALL_REQUIRES,
    packages=find_packages(),
    ext_modules=[
        PkgConfigNeededExtension(
            "{}._esys_binding".format(IMPORT_NAME),
            [os.path.join(IMPORT_NAME, "swig", "esys_binding.i")],
            pkg_config_cflags=["tss2-esys", "tss2-rc", "tss2-tctildr"],
            pkg_config_libs=["tss2-esys", "tss2-rc", "tss2-tctildr"],
            swig_opts=["-py3", "-outdir", IMPORT_NAME],
        )
    ],
    py_modules=[IMPORT_NAME],
    cmdclass={"build_ext": BuildExtThenCopySWIGPy},
)