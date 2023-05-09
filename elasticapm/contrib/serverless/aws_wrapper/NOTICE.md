apm-agent-python Copyright 2013-2023 Elasticsearch BV

# Notice

This lambda layer contains several dependencies which have been vendored.

## urllib3

-   **author:** Andrey Petrov
-   **project url:** https://github.com/urllib3/urllib3
-   **license:** MIT License, https://opensource.org/licenses/MIT

          MIT License

          Copyright (c) 2008-2019 Andrey Petrov and contributors (see CONTRIBUTORS.txt)

          Permission is hereby granted, free of charge, to any person obtaining a copy
          of this software and associated documentation files (the "Software"), to deal
          in the Software without restriction, including without limitation the rights
          to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
          copies of the Software, and to permit persons to whom the Software is
          furnished to do so, subject to the following conditions:

          The above copyright notice and this permission notice shall be included in all
          copies or substantial portions of the Software.

          THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
          IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
          FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
          AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
          LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
          OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
          SOFTWARE.

## certifi

-   **author:** Kenneth Reitz
-   **project url:** https://github.com/certifi/python-certifi
-   **license:** Mozilla Public License 2.0, https://opensource.org/licenses/MPL-2.0

          This packge contains a modified version of ca-bundle.crt:

          ca-bundle.crt -- Bundle of CA Root Certificates

          Certificate data from Mozilla as of: Thu Nov  3 19:04:19 2011#
          This is a bundle of X.509 certificates of public Certificate Authorities
          (CA). These were automatically extracted from Mozilla's root certificates
          file (certdata.txt).  This file can be found in the mozilla source tree:
          http://mxr.mozilla.org/mozilla/source/security/nss/lib/ckfw/builtins/certdata.txt?raw=1#
          It contains the certificates in PEM format and therefore
          can be directly used with curl / libcurl / php_curl, or with
          an Apache+mod_ssl webserver for SSL client authentication.
          Just configure this file as the SSLCACertificateFile.#

          ***** BEGIN LICENSE BLOCK *****
          This Source Code Form is subject to the terms of the Mozilla Public License,
          v. 2.0. If a copy of the MPL was not distributed with this file, You can obtain
          one at http://mozilla.org/MPL/2.0/.

          ***** END LICENSE BLOCK *****
          @(#) $RCSfile: certdata.txt,v $ $Revision: 1.80 $ $Date: 2011/11/03 15:11:58 $

## wrapt

-   **author:** Graham Dumpleton
-   **project url:** https://github.com/GrahamDumpleton/wrapt
-   **license:** BSD-2-Clause, http://opensource.org/licenses/BSD-2-Clause

          Copyright (c) 2013, Graham Dumpleton
          All rights reserved.

          Redistribution and use in source and binary forms, with or without
          modification, are permitted provided that the following conditions are met:

          * Redistributions of source code must retain the above copyright notice, this
            list of conditions and the following disclaimer.

          * Redistributions in binary form must reproduce the above copyright notice,
            this list of conditions and the following disclaimer in the documentation
            and/or other materials provided with the distribution.

          THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
          AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
          IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
          ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
          LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
          CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
          SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
          INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
          CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
          ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
          POSSIBILITY OF SUCH DAMAGE.
