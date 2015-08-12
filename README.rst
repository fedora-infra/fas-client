FAS client
==========

:Authors:   Xavier Lamien

FAS client is an remote cli tool which allow you to manage shell account
from fas user account.

.. contents::



Setup virtualenvwrapper
-----------------------
``sudo yum -y install python-virtualenvwrapper``

Add the following to your `~/.zshrc`::

    export WORKON_HOME=$HOME/.virtualenvs
    source /usr/bin/virtualenvwrapper.sh

Bootstrap the virtualenv
------------------------
**Dependencies**

 - libffi
 - openssl
 - GeoIP
 - libyaml


Fedora OS

::

    sudo dnf install -y libffi-devel openssl-devel GeoIP-devel libyaml-devel

::

    ./bootstrap.py
    workon fas-client-python2.7

Run the test suite
------------------
``python setup.py test``
NOTE: There's no test suite done at this time.


Run the web app
---------------
``fasClient --help``

