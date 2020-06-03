# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from sfconfig.components import Component  # type: ignore
from sfconfig.utils import execute  # type: ignore
from pathlib import Path
import typing


zk_ca_script = Path(__file__).resolve().parent / "zk-ca.sh"
zk_tls_root_path = Path("/var/lib/software-factory/bootstrap-data/zk-ca")
zk_ca_pem = zk_tls_root_path / "demoCA" / "cacert.pem"
zk_tls_crt = zk_tls_root_path / "certs" / "client.pem"
zk_tls_key = zk_tls_root_path / "keys" / "clientkey.pem"
zk_ca_files = [zk_ca_pem, zk_tls_crt, zk_tls_key]


def run_zk_ca_script(arg: str) -> None:
    execute([str(zk_ca_script), str(zk_tls_root_path), arg])


class Zookeeper(Component):  # type: ignore
    role = "zookeeper"

    def configure(self, args: typing.Any, host: typing.Dict[str, str]) -> None:
        zk_tls_root_path.mkdir(parents=True, exist_ok=True)

        def setup() -> None:
            # Client certs
            if not all(map(lambda x: x.exists(), zk_ca_files)):
                print("Creating initial zk-ca")
                run_zk_ca_script(host["hostname"])
            args.glue["zk_client_crt"] = zk_tls_crt.read_text()
            args.glue["zk_client_key"] = zk_tls_key.read_text()
            args.glue["zk_ca_pem"] = zk_ca_pem.read_text()

            # Server certs
            if "zk_keys" not in args.glue:
                args.glue["zk_keys"] = dict()
            server_key = zk_tls_root_path / "keystores" / (
                host["hostname"] + ".pem")
            if not server_key.exists():
                run_zk_ca_script(host["hostname"])
            args.glue["zk_keys"][host["hostname"]] = server_key.read_text()

        try:
            setup()
        except Exception:
            print("Failed to setup zookeeper CA")
            exit(1)
