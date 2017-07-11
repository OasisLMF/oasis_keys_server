# oasis_keys_server

A Flask application used to implement Oasis model keys servers.

The package documentation can be found at https://oasislmf.github.io/oasis_keys_server/.

## First steps

After cloning the repository (see the GitHub instructions on repository home page) and entering the repository folder you should install the package requirements using

    sudo pip install -r requirements.txt
    
(You may need to omit the `sudo` if you are in a virtualenv.)

Provided that `sys.path` contains the absolute path to the repository folder you can now import the package or its components in the normal way.

## Sphinx docs

This repository is enabled with <a href="https://pypi.python.org/pypi/Sphinx" target="_blank">Sphinx</a> documentation for the Python modules, and the documentation is published to

    https://oasislmf.github.io/oasis_keys_server/

on a fresh build. Firstly, to work on the Sphinx docs for this package you must have Sphinx installed on your system or in your `virtualenv` environment (recommended).

The Sphinx documentation source files are reStructuredText files, and are contained in the `docs` subfolder, which also contains the Sphinx configuration file `conf.py` and the `Makefile` for the build. To do a new build run

    make html

in the `docs` folder. You should see a new set of HTML files and assets in the `_build/html` subfolder (the build directory can be changed to `docs` itself in the `Makefile` but that is not recommended). Now copy the files to the docs folder using

    cp -R _build/html/* .

Add and `git` commit the new files, and GitHub pages will automatically  publish the new documents to site https://oasislmf.github.io/oasis_keys_server/.
