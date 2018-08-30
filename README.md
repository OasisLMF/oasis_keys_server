<img src="https://oasislmf.org/packages/oasis_theme_package/themes/oasis_theme/assets/src/oasis-lmf-colour.png" alt="Oasis LMF logo" width="250"/>

# oasis_keys_server

Flask app used to implement Oasis model keys servers.
Includes the `oasis_keys_lookup` subpackage containing base classes that as serve as templates/interfaces for model keys lookup classes.

# Varients 

* builtin - A built-in generic lookup that combines a peril lookup which uses Rtree spatial indexes and a vulnerability lookup which uses a simple key-value approach using dictionaries.

* custom - A lookup service which is tailored to a model, based on a custom python based lookup class. 


# First Steps

After cloning the repository (see the GitHub instructions on repository home page) and entering the repository folder you should install the package requirements using

    sudo pip install -r requirements.txt

(You may need to omit the `sudo` if you are in a virtual environment.)

Provided that `sys.path` contains the absolute path to the repository folder you can now import the package or its components in the normal way.

## Documentation
* <a href="https://oasislmf.github.io">General Oasis documentation</a>
* <a href="http://oasislmf.github.io/html/oasis_keys_server/modules.html">Modules</a>

## License
The code in this project is licensed under BSD 3-clause license.
