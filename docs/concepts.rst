Concepts
========

I/O with the proxy
__________________

The *portal* application runs a Flask_ endpoint listening on TCP 9000. It listens for shell requests and runs them
in a temporary directory.

You can access the *portal* from the outside world by simply CURLing commands with a **POST /shell**. The shell
snippet is passed via the **X-Shell** header. You can for instance run the *ls* tool:

.. code:: bash

    $ curl -X POST -H "X-Shell: ls" http://<IP>:9000/shell
    {"ok": true, "ms": 463, "out": "\n1 pods, 100% running ->\n - default.ocho-proxy #1\n"}

You can upload files as well (for instance when deploying clusters). The files will land in the temporary directory
and be wiped out as soon as the tool completes. Just use a regular multi-part upload, for instance:

.. code:: bash

    $ curl -X POST -H "X-Shell: deploy redis -p 3" -F "redis=@redis.yml" http://<IP>:9000/shell

.. note::

    Local directories will also be uploaded as TAR/GZIP archives.

The response is a serialized JSON object featuring the raw stdout dump of whatever tool you ran. It is thus quite
trivial to build a shallow CLI front-end on your end to interact with the remote shell. Any failure will set the *ok*
boolean to false (e.g non-zero exit code from the tool process).

SHA1-HMAC challenges
____________________

The proxy supports an optional security check. If a secret token is specified when deploying the container any REST
call to the proxy will have to incude a **X-Signature** header set to the SHA1 digest of the command line. Not setting
this header or setting it to something incorrect will result in a failure.

.. code:: bash

    $ curl -X POST -H "X-Shell: ls" -H "X-Signature: sha1=dha3jf861hbs781" http://<IP>:9000/shell


.. _Flask: http://flask.pocoo.org/

