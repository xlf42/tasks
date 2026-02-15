from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from string import Template

import pprint
from markdown_it import MarkdownIt

import config
import tasks
import qrcode

LISTENING_PORT = 9000


class RequestHandler(BaseHTTPRequestHandler):

    def _show_page(self, task, template):
        """
        create the page to show for an action on a task
        """
        # we initialize the markdown parser
        md = MarkdownIt()
        template = open(f"templates/{template}").read()
        # in case the when field is a list, we create multiple lines
        if isinstance(task["when"], list):
            task["when"] = "\n".join(task["when"])
        # we render the when field as markdown
        task["when"] = md.render(task["when"])
        if isinstance(task["description"], list):
            task["description"] = "\n".join(task["description"])
        task["description"] = md.render(task["description"])
        task["remaining_vetoes"] = tasks.get_remaining_vetoes(task["user"])
        if task["remaining_vetoes"] == 0:
            task["remaining_vetoes"] = "keinen"
        task["used_vetoes"] = config.read_config()["vetoes"] - task["remaining_vetoes"]
        if task["used_vetoes"] == 0:
            task["used_vetoes"] = "keinen"
        # we get the task status to display it
        task["status"] = tasks.get_task_status(task)
        response = Template(template).substitute(task).encode("utf-8")
        self.wfile.write(response)

    def _veto_task(self, user, id, task):
        """
        Prepare data and display web page for vetoing a task.
        """

        self.send_response(200)
        self.end_headers()
        # depending on success or failure, we show a different page
        if not tasks.veto_task(user, id):
            self._show_page(task, "task_veto_fail.tpl")
        else:
            self._show_page(task, "task_veto.tpl")
        return

    def _do_task(self, user, id, task):
        """
        Prepare data and display web page for vetoing a task.
        """
        self.send_response(200)
        self.end_headers()
        tasks.do_task(user=user, id=id)
        self._show_page(task, "task_done.tpl")

        return

    def _show_task(self, user, id, task):
        """
        Prepare data and display web page for showing a task.
        """
        result = tasks.show_task(
            user=user,
            id=id,
        )
        self.send_response(200)
        self.end_headers()
        if result["id"] != task["id"]:
            result["user"] = user
            result["token"] = task["token"]
            self._show_page(result, "task_show_pending.tpl")
        elif result["id"] == task["id"]:
            task_status = tasks.get_task_status(task)
            if task_status == "Abgelehnt":
                self._show_page(task, "task_show_vetoed.tpl")
            elif task_status == "Erledigt":
                self._show_page(task, "task_show_done.tpl")
            else:
                self._show_page(task, "task_show.tpl")
        else:
            self._show_page(result, "task_show_not_found.tpl")

    def _help(self, user, id, task):
        """
        Show the help text in the template tasks_help.tpl
        """
        tasks.store_help(user=user, task=task)
        self.send_response(200)
        self.end_headers()
        self._show_page(task, "tasks_help.tpl")

    def _list_vouchers(self, user, token, task_list, url):
        """
        Get the list of vouchers for a user.
        """
        self.send_response(200)
        self.end_headers()
        content = {}
        protocol = "http://"
        table_content = """"
        <table>
        <tr>
            <th>Title</th>
            <th>QR-Code</th>
            <th>Link</th>
        </tr>
        """
        for idx, task in enumerate(task_list):
            title = task["title"]
            task_url = protocol + url + f"/tasks/show?id={idx}&token={token}"
            img_url = protocol + url + f"/tasks/qrcode?token={token}&url={task_url}"
            table_row = """<tr>
                <td>{title}</td>
                <td><img src="{img_url}" alt="QR Code" height="50" width="50"/></td>
                <td><a href="{task_url}">{task_url}</a></td>
            </tr>
            """
            table_content += table_row.format(
                title=title, task_url=task_url, img_url=img_url
            )

        table_content += """
        </table>
        """
        content["table_content"] = table_content
        content["user"] = user
        content["token"] = token
        response = (
            Template(open("templates/task_vouchers.tpl").read())
            .substitute(content)
            .encode("utf-8")
        )
        self.wfile.write(response)
        return

    def do_GET(self):
        parsed_url = urlparse(self.path)
        path_parts = parsed_url.path.strip("/").split("/")
        query_params = parse_qs(parsed_url.query)
        # we extract the full URL for display purposes
        url = ""
        for h in self.headers._headers:
            if h[0] == "Host":
                url = h[1]

        if not path_parts or not path_parts[0]:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Module name required")
            return

        module_name = path_parts[path_parts.index("tasks") + 1]

        if "token" not in query_params:
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"Token required")
            return
        token = query_params["token"][0]
        cfg = config.read_config()
        user = config.get_user_from_token(cfg, token)
        if not user:
            self.send_response(403)
            self.end_headers()
            self.wfile.write(b"Invalid token")
            return

        id = None
        task = {}

        # having a user, we can load the task list
        task_list = tasks.list_tasks(user=user)
        # if we want to show, do or veto a task, we need to load it first
        if "id" in query_params:
            id = int(query_params["id"][0])
            if id >= len(task_list):
                self.send_response(200)
                self.end_headers()
                pending = tasks.get_pending_task(user)
                if pending is not None:
                    pending["token"] = token
                    pending["user"] = user
                    self._show_page(pending, "task_not_found_pending.tpl")
                    return
                else:
                    self._show_page(
                        {"token": token, "user": user}, "task_not_found.tpl"
                    )
                    return
            task = task_list[id]
            task["token"] = token
            task["user"] = user
            task["index"] = id

        if module_name == "debug":
            if self.protocol_version == "HTTP/1.1":
                protocol = "http://"
            else:
                protocol = "https://"
            self.send_response(200)
            self.end_headers()
            all_task_list = tasks.list_all_tasks()
            content = {
                "protocol": self.protocol_version,
                "url": protocol + url,
                "server": self.server.server_name + ":" + str(self.server.server_port),
                "request_path": self.path,
                "request_data": "<pre>" + pprint.pformat(query_params) + "</pre>",
                "task_data": "<pre>" + pprint.pformat(all_task_list) + "</pre>",
                "config_data": "<pre>" + pprint.pformat(cfg) + "</pre>",
            }
            response = (
                Template(open("templates/task_debug.tpl").read())
                .substitute(content)
                .encode("utf-8")
            )
            self.wfile.write(response)
            return
        elif module_name == "voucher":
            self._list_vouchers(user=user, token=token, task_list=task_list, url=url)
            return
        elif module_name == "qrcode":
            self.send_response(200)
            self.send_header("Content-type", "image/png")
            self.end_headers()
            qr_url = query_params.get("url", [""])[0]
            if not qr_url:
                self.wfile.write(b"URL parameter required")
                return
            qr_url += f"&token={token}"
            qr = qrcode.QRCode()
            qr.add_data(qr_url)
            qr.make()
            img = qr.make_image()
            img.save(self.wfile, format="PNG")
            return
        elif module_name == "list":
            self.send_response(200)
            self.end_headers()
            content = {}
            # starting the table
            tablecontent = """
            <table>
            <tr>
                <th>ID</th>
                <th>Description</th>
                <th>When</th>
                <th>Shown</th>
                <th>Done</th>
                <th>Vetoed</th>
            </tr>
            """
            for task in task_list:
                if isinstance(task["when"], list):
                    task["when"] = "\n".join(task["when"])
                if isinstance(task["description"], list):
                    task["description"] = "\n".join(task["description"])
                tablecontent += f"""
                <tr>
                    <td>{task["id"]}</td>
                    <td>{task["description"]}</td>
                    <td>{task["when"]}</td>
                    <td>{task.get("shown_at", "N/A")}</td>
                    <td>{task.get("done_at", "N/A")}</td>
                    <td>{task.get("vetoed_at", "N/A")}</td>
                </tr>
                """
            # finalize the table
            tablecontent += """
            </table>
            """
            content["task_table"] = tablecontent
            response = (
                Template(open("templates/task_list.tpl").read())
                .substitute(content)
                .encode("utf-8")
            )
            self.wfile.write(response)
            return

        help_needed = not tasks.get_help_status(user=user)

        if help_needed or module_name == "help":
            self._help(user=user, id=id, task=task)
        elif module_name == "show":
            self._show_task(user=user, id=id, task=task)
            return
        elif module_name == "do":
            self._do_task(user=user, id=id, task=task)
            return
        elif module_name == "veto":
            self._veto_task(user=user, id=id, task=task)
            return
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Module not found")
            return

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    server_address = ("", LISTENING_PORT)
    httpd = HTTPServer(server_address, RequestHandler)
    print(f"Starting server on port {LISTENING_PORT}...")
    httpd.serve_forever()
