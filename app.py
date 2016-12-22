import json
import logging
import aiohttp_jinja2
import jinja2
import os
from aiohttp import web
from aiohttp_ac_hipchat.addon_app import create_addon_app
import asyncio
from util import HtmlNotification
from util import RoomNotificationArgumentParser
from alias_controller import AliasController, validate_mention_name

SCOPES_V1 = ["view_group", "send_notification", "admin_room"]
SCOPES_V2 = ["view_group", "send_notification", "admin_room", "view_room"]

def get_scopes(context):
    return SCOPES_V2 if context.get("hipchat_server", False) else SCOPES_V1

FROM_NAME = "HipAlias"
PARTICIPANTS_CACHE_KEY = "hipchat-participants:{group_id}:{room_id}"

log = logging.getLogger(__name__)
app, addon = create_addon_app(addon_key="HipAlias",
                       addon_name="HipAlias",
                       vendor_name="Oxalide",
                       vendor_url="http://oxalide.com",
                       from_name=FROM_NAME,
                       scopes=get_scopes)

static_folder = os.path.join(os.path.dirname(__file__), 'assets')
static_route = app.router.add_static('/assets', static_folder, name='static')

alias_controller = AliasController(app["config"]["BASE_URL"], app['mongodb']['aliases'])

@asyncio.coroutine
def init(app):
    @asyncio.coroutine
    def send_welcome(event):
        client = event['client']
        asyncio.async(client.room_client.send_notification(text="HipAlias was added to this room"))

    @asyncio.coroutine
    def register_existing_alias(client, alias):

        new_alias = yield from alias_controller.add_alias(client, alias["alias"], alias["mentions"], delete_existing=False)
        if new_alias:
            log.info("Existing Alias %s re-registered" % alias["alias"])
        else:
            log.error("Problem registering webhook")

    @asyncio.coroutine
    def register_existing_aliases(event):
        client = event['client']
        aliases = yield from alias_controller.find_all_alias(client)
        log.info("Found {0} existing aliases. Registering webhooks for them".format(len(aliases)))
        for alias in aliases:
            asyncio.async(register_existing_alias(client, alias))

    app['addon'].register_event('install', send_welcome)
    app['addon'].register_event('install', register_existing_aliases)

def init_jinja2():
    jinja2_env = aiohttp_jinja2.setup(app, autoescape=True,
                                      loader=jinja2.FileSystemLoader(os.path.join(os.path.dirname(__file__), 'views')))

    def url_for(route, filename):
        parameters = {}
        if "static" == route and app["config"]["DEBUG"]:
            parameters["hash"] = static_file_hash(os.path.join(static_folder, filename))

        return app.router[route].url(filename=filename, query=parameters)

    def static_file_hash(filename):
        return int(os.stat(filename).st_mtime)

    jinja2_env.globals['url_for'] = url_for

init_jinja2()
app.add_hook("before_first_request", init)


addon.add_action_capability({
    "key": "alias.input.action",
    "name": {
        "value": "Find an alias"
    },
    "target": {
        "type": "dialog",
        "key": "alias.dialog"
    },
    "location": "hipchat.input.action",
    "url": app["config"]["BASE_URL"] + "/dialog"
})

@asyncio.coroutine
@addon.webhook("room_message", path="/alias", pattern="^/alias(\s|$).*", auth=None)
def alias(request):
    addon = request.app['addon']
    body = yield from request.json()
    client_id = body['oauth_client_id']
    client = yield from addon.load_client(client_id)

    parser = _create_parser(client, request)

    yield from parser.handle_webhook(body)

    return web.HTTPNoContent()


@asyncio.coroutine
@addon.dialog("alias.dialog", "Choose alias", path="/dialog",
              options={
                  "size": {
                      "width": "600px",
                      "height": "240px"
                  }
              })
@aiohttp_jinja2.template('dialog.jinja2')
def dialog(request):

    return {
        "base_url": app["config"]["BASE_URL"],
        "signed_request": request.token,
    }

@asyncio.coroutine
@addon.require_jwt()
def get_aliases(request):
    results = []
    aliases = yield from alias_controller.find_all_alias(request.client)
    for alias in aliases:
        results.append({
            "alias": alias["alias"],
            "mentions": alias["mentions"],
        })

    return web.Response(text=json.dumps(results))

@asyncio.coroutine
@addon.require_jwt()
def delete_alias(request):
    alias_name = request.match_info['alias_name']
    yield from alias_controller.remove_alias(request.client, alias_name)

    return web.HTTPOk()

@asyncio.coroutine
@addon.require_jwt()
def add_alias(request):
    alias_name = request.match_info['alias_name']
    body = yield from request.json()

    yield from alias_controller.add_alias(request.client, alias_name, body["mentions"])
    aliases = yield from get_aliases(request)
    return aliases


@asyncio.coroutine
@addon.require_jwt()
def edit_alias(request):
    alias_name = request.match_info['alias_name']
    body = yield from request.json()

    client = request.client
    yield from alias_controller.edit_alias(client, alias_name, body["mentions"])

    return web.HTTPOk()

@asyncio.coroutine
def mention(request):
    alias_name = request.match_info['alias_name']

    addon = request.app['addon']
    body = yield from request.json()
    client_id = body['oauth_client_id']
    client = yield from addon.load_client(client_id)

    existing = yield from alias_controller.find_alias(client, alias_name)
    if existing:
        mentions = existing['mentions']

        txt = " {{mentions}} <br /> <strong> {{ original }} </strong> ".format(
            original=body['item']["message"]["message"],
            mentions=" ".join(mentions))
        from_mention = body['item']['message']['from']['mention_name']
        yield from client.room_client.send_notification(from_mention=from_mention, text=txt, notify=True)

        return web.HTTPNoContent()
    else:
        log.error("Mention name '%s' not found for client %s" % (alias_name, client_id))
        return web.HTTPBadRequest()

@asyncio.coroutine
@addon.require_jwt()
def get_room_participants(request):

    redis_pool = app['redis_pool']
    room_id = request.jwt_data["context"]["room_id"]
    cache_key = PARTICIPANTS_CACHE_KEY.format(group_id=request.client.group_id, room_id=room_id)
    cached_data = (yield from redis_pool.get(cache_key))
    results = json.loads(cached_data) if cached_data else None

    if not results:
        participants = yield from request.client.room_client.get_participants(room_id)

        results = []
        for participant in participants:
            results.append({
                "id": participant["id"],
                "mention_name": participant["mention_name"]
            })

        yield from redis_pool.setex(key=cache_key, value=json.dumps(results), seconds=30)

    return web.Response(text=json.dumps(results))


def _create_parser(client, request):

    @asyncio.coroutine
    def list_aliases(_):
        aliases = yield from alias_controller.find_all_alias(client)
        if not aliases:
            return "No aliases registered. Register one with '/alias set @ALIAS @MENTION...'"
        else:
            return "Aliases registered: %s" % ", ".join([a['alias'] for a in aliases])

    @asyncio.coroutine
    def set_alias(args):
        try:
            for item in args.mentions + [args.alias]:
                validate_mention_name(item)
        except ValueError as e:
            return str(e)

        new_alias = yield from alias_controller.add_alias(client, args.alias, args.mentions)
        if new_alias:
            return "Alias %s added" % args.alias
        else:
            return "Problem registering webhook"

    @asyncio.coroutine
    def remove_alias(args):
        try:
            validate_mention_name(args.alias)
        except ValueError as e:
            return str(e)

        deleted_alias = yield from alias_controller.remove_alias(client, args.alias)
        if deleted_alias:
            return "Alias %s removed" % args.alias
        else:
            return "Alias %s not found" % args.alias

    @asyncio.coroutine
    def show_alias(args):
        try:
            validate_mention_name(args.alias)
        except ValueError as e:
            return str(e)

        existing = yield from alias_controller.find_alias(client, args.alias)
        if existing and 'webhook_url' in existing:
            mentions = ['&commat;%s' % x[1:] for x in existing['mentions']]
            return HtmlNotification("Alias %s is mapped to %s" % (args.alias, " ".join(mentions)))
        else:
            return "Alias %s not found" % args.alias

    parser = RoomNotificationArgumentParser(app, "/alias", client)
    subparsers = parser.add_subparsers(help='Available commands')

    subparsers.add_parser('list', help='List existing aliases', handler=list_aliases)

    parser_set = subparsers.add_parser('set', help='Sets a group mention alias', handler=set_alias)
    parser_set.add_argument('alias', metavar='@ALIAS', type=str, help='The mention alias, beginning with an "@"')
    parser_set.add_argument('mentions', metavar='@MENTION', nargs='+', type=str,
                            help='The mention names, beginning with an "@"')

    parser_set = subparsers.add_parser('remove', help='Removes a group mention alias', handler=remove_alias)
    parser_set.add_argument('alias', metavar='@ALIAS', type=str, help='The mention alias, beginning with an "@"')

    parser_show = subparsers.add_parser('show', help='Shows the names for an existing alias', handler=show_alias)
    parser_show.add_argument('alias', metavar='@ALIAS', type=str, help='The mention alias, beginning with an "@"')

    return parser

app.router.add_route('POST', '/alias/{alias_name}', add_alias)
app.router.add_route('PUT', '/alias/{alias_name}', edit_alias)
app.router.add_route('DELETE', '/alias/{alias_name}', delete_alias)
app.router.add_route('GET', '/alias', get_aliases)
app.router.add_route('POST', '/mention/{alias_name}', mention)
app.router.add_route('GET', '/room_participants', get_room_participants)
