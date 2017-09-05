`oasis_keys_server`
==================

`oasis_keys_server` is a Flask app used to implement Oasis model keys servers.

The package documentation can be found at https://oasislmf.github.io/oasis_keys_server/.

# Repository Management

## Cloning the repository

You can clone this repository from <a href="https://github.com/OasisLMF/oasis_keys_server" target="_blank">GitHub</a> using HTTPS or SSH, but it is recommended that that you use SSH: first ensure that you have generated an SSH key pair on your local machine and add the public key of that pair to your GitHub account (use the GitHub guide at https://help.github.com/articles/connecting-to-github-with-ssh/). Then run

    git clone git+ssh://git@github.com/OasisLMF/oasis_keys_server

To clone over HTTPS use

    git clone https://github.com/OasisLMF/oasis_keys_server

You may receive a password prompt - to bypass the password prompt use

    git clone https://<GitHub user name:GitHub password>@github.com/OasisLMF/oasis_keys_server

# Sphinx Docs

This repository is enabled with <a href="https://pypi.python.org/pypi/Sphinx" target="_blank">Sphinx</a> documentation for the Python modules, and the documentation is published to <a href="https://oasislmf.github.io/OasisLMF/oasis_keys_server/" target="_blank">https://oasislmf.github.io/oasis_keys_server/</a> automatically via GitHub pages on updates to the GitHub repository.

## Setting up Sphinx

Firstly, to work on the Sphinx docs for this package you must have Sphinx installed on your system or in your virtual environment (`virtualenv` is recommended).

You should also clone the Oasis publication repository <a href="https://github.com/OasisLMF/OasisLMF.github.io" target="_blank">OasisLMF.github.io</a>.

## Building and publishing

The Sphinx documentation source files are reStructuredText files, and are contained in the `docs` subfolder, which also contains the Sphinx configuration file `conf.py` and the `Makefile` for the build. To do a new build make sure you are in the `docs` subfolder and run

    make html

You should see a new set of HTML files and assets in the `_build/html` subfolder (the build directory can be changed to `docs` itself in the `Makefile` but that is not recommended). The `docs` subfolder should always contain the latest copy of the built HTML and assets so first copy the files from `_build/html` to `docs` using

    cp -R _build/html/* .

Add and commit these files to the local repository, and then update the remote repository on GitHub - GitHub pages will automatically publish the new documents to the documentation site https://oasislmf.github.io/oasis_keys_server/.

# First Steps

After cloning the repository (see the GitHub instructions on repository home page) and entering the repository folder you should install the package requirements using

    sudo pip install -r requirements.txt

(You may need to omit the `sudo` if you are in a virtual environment.)

Provided that `sys.path` contains the absolute path to the repository folder you can now import the package or its components in the normal way.
