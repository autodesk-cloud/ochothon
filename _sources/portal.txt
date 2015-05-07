Portal
======

The shell
_________

CURL
****

The *portal* application runs a Flask_ endpoint listening on TCP 9000. It listens for shell requests and runs them
in a temporary directory. Each request must map to one our tools.

You can access the *portal* from the outside world by simply CURLing commands with a **POST /shell**. The shell
snippet is passed via the **X-Shell** header. You can for instance run the *ls* tool this way:

.. code:: bash

    $ curl -X POST -H "X-Shell:ls" http://52.6.130.234:9000/shell
    {"ok": true, "ms": 463, "out": "\n1 pods, 100% running ->\n - default.ocho-proxy #1\n"}

You can upload files as well (for instance when deploying clusters). The files will land in the temporary directory
and be wiped out as soon as the tool completes. Just use a regular multi-part upload, for instance:

.. code:: bash

    $ curl -X POST -H "X-Shell:deploy redis -p 3" -F "redis=@redis.yml" http://52.6.130.234:9000/shell

The response is a serialized JSON object featuring the raw stdout dump of whatever tool you ran. It is thus quite
trivial to build a shallow CLI front-end on your end to interact with the remote shell. Any failure will set the *ok*
boolean to false (e.g non-zero exit code from the tool process).

.. note::

    Some tools will require that one or more files be uploaded (**deploy** for instance).

Using a browser
***************

The *portal* will also return HTML on TCP 9000 for a **GET /**. We serve back a simple JQuery_ terminal that will allow
you to interactively perform the same shell calls via AJAX.


.. _Flask: http://flask.pocoo.org/
.. _JQuery: https://jquery.com/
.. _Ochopod: https://github.com/autodesk-cloud/ochopod
.. _Python: https://www.python.org/

