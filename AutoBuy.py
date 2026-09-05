# ba_meta require api 9

from __future__ import annotations

import re

import bascenev1 as ba
import babase
import bauiv1 as bui
from bauiv1lib import party


MOD_NAME = 'AutoBuy'

CREATOR_TEXT = (
    'Mod:AutoBuy Creator:Belingham '
    'Id Telegram:@Darkofgang: ON'
)

CANCEL_COMMAND = 'AutoBuy.Belingham.Cancel'

AUTO_BUY_ENABLED = True

_AUTO_BUY_PLUGIN = None
_AUTO_BUY_SETTINGS_WINDOW = None

ITEM_LIMITS = {}
AUTOBUY_CONFIG_KEY = 'BSLifeAutoBuy_ItemLimits'


# ============================================================
# PATTERNS
# ============================================================

SELL_PATTERN = re.compile(
    r'Sell\s*ID\s*:\s*(s\d+)',
    re.IGNORECASE,
)

BUY_RESULT_PATTERN = re.compile(
    r"""
    \b(?P<id>s\d+)\s*:
    .*?
    <
    \s*(?P<amount>\d+)
    \s+(?P<code>[A-Za-z0-9_]+)
    \s*>
    .*?
    \bfor\s+
    (?P<total>[\d,]+)
    \s+coins
    .*?
    \bOk\s*=\s*1
    """,
    re.IGNORECASE | re.VERBOSE,
)


# ============================================================
# SETTINGS LOAD / SAVE
# ============================================================

def _load_item_limits():
    global ITEM_LIMITS

    try:
        saved = babase.app.config.get(
            AUTOBUY_CONFIG_KEY,
            {},
        )

        ITEM_LIMITS.clear()

        if isinstance(saved, dict):
            for code, price in saved.items():
                try:
                    ITEM_LIMITS[
                        str(code).strip().lower()
                    ] = float(price)
                except (TypeError, ValueError):
                    pass

    except Exception as exc:
        print(
            'AUTOBUY LOAD ERROR:',
            repr(exc),
        )


def _save_item_limits():
    try:
        babase.app.config[
            AUTOBUY_CONFIG_KEY
        ] = {
            str(code).strip().lower(): float(price)
            for code, price in ITEM_LIMITS.items()
        }

        babase.app.config.commit()

    except Exception as exc:
        print(
            'AUTOBUY SAVE ERROR:',
            repr(exc),
        )


# ============================================================
# CHAT
# ============================================================

def _read_chat():
    try:
        messages = ba.get_chat_messages()

        if not messages:
            return []

        return [
            str(x).strip()
            for x in messages
        ]

    except Exception:
        return []


# ============================================================
# HELPERS
# ============================================================

def _normalize_code(code):
    return str(code).strip().lower()


def _format_price(value):
    try:
        value = float(value)

        if value.is_integer():
            return str(int(value))

        return '{:.2f}'.format(value)

    except Exception:
        return str(value)


# ============================================================
# SETTINGS WINDOW
# ============================================================

class AutoBuySettingsWindow:

    def __init__(self):

        global _AUTO_BUY_SETTINGS_WINDOW

        self._root_widget = bui.containerwidget(
            size=(520, 440),
            transition='in_scale',
        )

        bui.textwidget(
            parent=self._root_widget,
            position=(0, 390),
            size=(520, 35),
            text='AUTO BUY SETTINGS',
            h_align='center',
            v_align='center',
            scale=1.0,
        )

        bui.textwidget(
            parent=self._root_widget,
            position=(20, 365),
            size=(480, 22),
            text=CREATOR_TEXT,
            h_align='center',
            v_align='center',
            scale=0.42,
        )

        bui.textwidget(
            parent=self._root_widget,
            position=(40, 325),
            size=(200, 30),
            text='Item Code',
            h_align='center',
            v_align='center',
            scale=0.75,
        )

        self._code_field = bui.textwidget(
            parent=self._root_widget,
            position=(40, 275),
            size=(200, 45),
            editable=True,
            text='',
            h_align='center',
            v_align='center',
            scale=0.85,
        )

        bui.textwidget(
            parent=self._root_widget,
            position=(280, 325),
            size=(200, 30),
            text='Max Unit Price',
            h_align='center',
            v_align='center',
            scale=0.70,
        )

        self._price_field = bui.textwidget(
            parent=self._root_widget,
            position=(280, 275),
            size=(200, 45),
            editable=True,
            text='',
            h_align='center',
            v_align='center',
            scale=0.85,
        )

        bui.buttonwidget(
            parent=self._root_widget,
            position=(145, 215),
            size=(230, 50),
            label='ADD / UPDATE',
            button_type='square',
            autoselect=True,
            text_scale=0.65,
            on_activate_call=bui.Call(
                self._add_update
            ),
        )

        bui.textwidget(
            parent=self._root_widget,
            position=(40, 180),
            size=(440, 30),
            text='CURRENT ITEMS',
            h_align='center',
            v_align='center',
            scale=0.75,
        )

        self._list_text = bui.textwidget(
            parent=self._root_widget,
            position=(45, 65),
            size=(430, 110),
            text='',
            h_align='left',
            v_align='top',
            scale=0.70,
        )

        close_button = bui.buttonwidget(
            parent=self._root_widget,
            position=(180, 12),
            size=(160, 42),
            label='CLOSE',
            button_type='square',
            autoselect=True,
            text_scale=0.65,
            on_activate_call=bui.Call(
                self._close
            ),
        )

        try:
            bui.containerwidget(
                edit=self._root_widget,
                cancel_button=close_button,
            )
        except Exception:
            pass

        self._update_list()

    def _add_update(self):

        try:
            code = str(
                bui.textwidget(
                    query=self._code_field
                )
            ).strip()

            price_text = str(
                bui.textwidget(
                    query=self._price_field
                )
            ).strip()

        except Exception:
            return

        if not code:
            ba.screenmessage(
                'ENTER ITEM CODE',
                color=(1.0, 0.3, 0.3),
            )
            return

        if not price_text:
            ba.screenmessage(
                'ENTER MAX UNIT PRICE',
                color=(1.0, 0.3, 0.3),
            )
            return

        try:
            price = float(price_text)

        except Exception:
            ba.screenmessage(
                'INVALID PRICE',
                color=(1.0, 0.3, 0.3),
            )
            return

        if price < 0:
            return

        code = _normalize_code(code)

        ITEM_LIMITS[code] = price

        _save_item_limits()

        ba.screenmessage(
            '{} <= {} coins/unit'.format(
                code,
                _format_price(price),
            ),
            color=(0.2, 1.0, 0.2),
        )

        try:
            bui.textwidget(
                edit=self._code_field,
                text='',
            )

            bui.textwidget(
                edit=self._price_field,
                text='',
            )

        except Exception:
            pass

        self._update_list()

    def _update_list(self):

        if not ITEM_LIMITS:
            text = 'No items configured.'

        else:
            text = '\n'.join(
                '{} <= {} coins/unit'.format(
                    code,
                    _format_price(price),
                )
                for code, price in ITEM_LIMITS.items()
            )

        try:
            bui.textwidget(
                edit=self._list_text,
                text=text,
            )
        except Exception:
            pass

    def _close(self):

        global _AUTO_BUY_SETTINGS_WINDOW

        try:
            bui.containerwidget(
                edit=self._root_widget,
                transition='out_scale',
            )
        except Exception:
            pass

        _AUTO_BUY_SETTINGS_WINDOW = None


# ============================================================
# OPEN SETTINGS
# ============================================================

def _open_settings():

    global _AUTO_BUY_SETTINGS_WINDOW

    if _AUTO_BUY_SETTINGS_WINDOW is not None:
        return

    try:
        _AUTO_BUY_SETTINGS_WINDOW = (
            AutoBuySettingsWindow()
        )

    except Exception as exc:
        print(
            'SETTINGS OPEN ERROR:',
            repr(exc),
        )


# ============================================================
# BUY BUTTON
# ============================================================

def _update_buy_button(window):

    button = getattr(
        window,
        '_autobuy_button',
        None,
    )

    if button is None:
        return

    try:
        bui.buttonwidget(
            edit=button,
            label=(
                'BUY ON'
                if AUTO_BUY_ENABLED
                else 'BUY OFF'
            ),
        )

    except Exception:
        pass


def _toggle_buy(window):

    global AUTO_BUY_ENABLED

    AUTO_BUY_ENABLED = not AUTO_BUY_ENABLED

    plugin = _AUTO_BUY_PLUGIN

    if plugin is not None:

        if not AUTO_BUY_ENABLED:

            plugin._queue.clear()
            plugin._queued_ids.clear()

            plugin._waiting = False
            plugin._pending_id = None

            plugin._request_token += 1

    ba.screenmessage(
        'AUTO BUY: {}'.format(
            'ON'
            if AUTO_BUY_ENABLED
            else 'OFF'
        ),
        color=(
            (0.2, 1.0, 0.2)
            if AUTO_BUY_ENABLED
            else
            (1.0, 0.3, 0.3)
        ),
    )

    _update_buy_button(window)


# ============================================================
# PARTY WINDOW
# ============================================================

_previous_party_init = party.PartyWindow.__init__


def _autobuy_party_init(
    self,
    origin=(0, 0),
):

    _previous_party_init(
        self,
        origin,
    )

    try:

        if getattr(
            self,
            '_autobuy_added',
            False,
        ):
            return

        self._autobuy_added = True

        bui.textwidget(
            parent=self._root_widget,
            position=(20, 18),
            size=(380, 22),
            text=CREATOR_TEXT,
            h_align='left',
            v_align='center',
            scale=0.38,
        )

        self._autobuy_button = bui.buttonwidget(
            parent=self._root_widget,
            position=(425, 70),
            size=(90, 35),
            scale=0.75,
            label=(
                'BUY ON'
                if AUTO_BUY_ENABLED
                else 'BUY OFF'
            ),
            button_type='square',
            autoselect=True,
            text_scale=0.48,
            on_activate_call=bui.WeakCall(
                _toggle_buy,
                self,
            ),
        )

        bui.buttonwidget(
            parent=self._root_widget,
            position=(425, 113),
            size=(90, 35),
            scale=0.75,
            label='SETTINGS',
            button_type='square',
            autoselect=True,
            text_scale=0.43,
            on_activate_call=bui.Call(
                _open_settings
            ),
        )

    except Exception as exc:

        print(
            'AUTOBUY PARTY BUTTON ERROR:',
            repr(exc),
        )


if not getattr(
    party.PartyWindow,
    '_autobuy_init_patch',
    False,
):

    party.PartyWindow.__init__ = (
        _autobuy_party_init
    )

    party.PartyWindow._autobuy_init_patch = True


# ============================================================
# DIRECT CHAT HOOK
# ============================================================

_previous_party_chat = getattr(
    party.PartyWindow,
    'on_chat_message',
    None,
)


def _autobuy_chat_message(
    self,
    msg,
):

    if _previous_party_chat is not None:

        try:
            _previous_party_chat(
                self,
                msg,
            )

        except Exception as exc:

            print(
                'AUTOBUY OLD CHAT ERROR:',
                repr(exc),
            )

    plugin = _AUTO_BUY_PLUGIN

    if plugin is not None:

        try:
            plugin._handle_chat_message(msg)

        except Exception as exc:

            print(
                'AUTOBUY CHAT HOOK ERROR:',
                repr(exc),
            )


if (
    _previous_party_chat is not None
    and not getattr(
        party.PartyWindow,
        '_autobuy_chat_patch',
        False,
    )
):

    party.PartyWindow.on_chat_message = (
        _autobuy_chat_message
    )

    party.PartyWindow._autobuy_chat_patch = True


# ============================================================
# PLUGIN
# ============================================================

# ba_meta export babase.Plugin
class AutoBuy(babase.Plugin):

    def __init__(self):

        global _AUTO_BUY_PLUGIN

        _AUTO_BUY_PLUGIN = self

        _load_item_limits()

        self._queue = []
        self._queued_ids = set()

        self._active_sell_ids = set()

        self._waiting = False
        self._pending_id = None

        self._request_token = 0

        self._timer = babase.AppTimer(
            0.02,
            self._poll_chat,
            repeat=True,
        )

        self._result_timer = babase.AppTimer(
            0.02,
            self._check_buy_response,
            repeat=True,
        )

        ba.screenmessage(
            CREATOR_TEXT,
            color=(0.2, 1.0, 0.2),
        )

    # ========================================================
    # POLL CHAT
    # ========================================================

    def _poll_chat(self):

        if not AUTO_BUY_ENABLED:
            return

        messages = _read_chat()

        if not messages:

            self._active_sell_ids.clear()

            return

        current_sell_ids = set()

        for msg in messages:

            text = str(msg).strip()

            match = SELL_PATTERN.search(
                text
            )

            if not match:
                continue

            sell_id = _normalize_code(
                match.group(1)
            )

            current_sell_ids.add(
                sell_id
            )

            if sell_id not in self._active_sell_ids:

                self._enqueue_sell_id(
                    sell_id
                )

        self._active_sell_ids = (
            current_sell_ids
        )

    # ========================================================
    # CHAT HOOK
    # ========================================================

    def _handle_chat_message(self, msg):

        if not AUTO_BUY_ENABLED:
            return

        text = str(msg).strip()

        if not text:
            return

        match = SELL_PATTERN.search(
            text
        )

        if not match:
            return

        sell_id = _normalize_code(
            match.group(1)
        )

        if sell_id in self._active_sell_ids:
            return

        self._enqueue_sell_id(
            sell_id
        )

    # ========================================================
    # QUEUE
    # ========================================================

    def _enqueue_sell_id(self, sell_id):

        if not AUTO_BUY_ENABLED:
            return

        sell_id = _normalize_code(
            sell_id
        )

        if sell_id in self._queued_ids:
            return

        if self._pending_id == sell_id:
            return

        self._queue.append(
            sell_id
        )

        self._queued_ids.add(
            sell_id
        )

        ba.screenmessage(
            'QUEUE: {}'.format(
                sell_id
            ),
            color=(0.3, 0.8, 1.0),
        )

        self._process_next()

    # ========================================================
    # PROCESS NEXT
    # ========================================================

    def _process_next(self):

        if not AUTO_BUY_ENABLED:
            return

        if self._waiting:
            return

        if not self._queue:
            return

        sell_id = self._queue.pop(0)

        self._queued_ids.discard(
            sell_id
        )

        self._waiting = True

        self._pending_id = sell_id

        self._request_token += 1

        token = self._request_token

        ba.screenmessage(
            'CHECK {}'.format(
                sell_id
            ),
            color=(0.3, 0.8, 1.0),
        )

        try:

            ba.chatmessage(
                'b {}'.format(
                    sell_id
                )
            )

        except Exception as exc:

            print(
                'AUTOBUY BUY COMMAND ERROR:',
                repr(exc),
            )

            self._finish_request()

            return

        babase.apptimer(
            2.0,
            babase.Call(
                self._request_timeout,
                sell_id,
                token,
            ),
        )

    # ========================================================
    # TIMEOUT
    # ========================================================

    def _request_timeout(
        self,
        sell_id,
        token,
    ):

        if token != self._request_token:
            return

        if self._pending_id != sell_id:
            return

        if not self._waiting:
            return

        ba.screenmessage(
            'NO RESULT: {}'.format(
                sell_id
            ),
            color=(1.0, 0.7, 0.2),
        )

        self._finish_request()

    # ========================================================
    # CHECK RESPONSE
    # ========================================================

    def _check_buy_response(self):

        if not AUTO_BUY_ENABLED:
            return

        if not self._waiting:
            return

        if self._pending_id is None:
            return

        messages = _read_chat()

        if not messages:
            return

        for text in messages:

            self._check_result_text(
                text
            )

            if not self._waiting:
                break

    # ========================================================
    # PARSE RESPONSE
    # ========================================================

    def _check_result_text(self, text):

        if not self._waiting:
            return

        pending = self._pending_id

        if pending is None:
            return

        match = BUY_RESULT_PATTERN.search(
            str(text)
        )

        if not match:
            return

        sell_id = _normalize_code(
            match.group('id')
        )

        if sell_id != pending:
            return

        try:

            amount = int(
                match.group('amount')
            )

            item_code = _normalize_code(
                match.group('code')
            )

            total_price = int(
                match.group('total')
                .replace(',', '')
            )

        except Exception as exc:

            print(
                'AUTOBUY PARSE ERROR:',
                repr(exc),
            )

            self._finish_request()

            return

        if amount <= 0:

            self._finish_request()

            return

        unit_price = (
            float(total_price)
            / float(amount)
        )

        max_price = ITEM_LIMITS.get(
            item_code
        )

        ba.screenmessage(
            '{} x{} = {} | UNIT {}'.format(
                item_code,
                amount,
                total_price,
                _format_price(unit_price),
            ),
            color=(0.3, 0.9, 1.0),
        )

        print(
            'AUTOBUY RESULT:',
            sell_id,
            'ITEM:',
            item_code,
            'AMOUNT:',
            amount,
            'TOTAL:',
            total_price,
            'UNIT:',
            unit_price,
            'MAX:',
            max_price,
        )

        # ====================================================
        # NOT SET
        # ====================================================

        if max_price is None:

            ba.screenmessage(
                'NOT SET: {}'.format(
                    item_code
                ),
                color=(1.0, 0.7, 0.2),
            )

            self._finish_request()

            return

        # ====================================================
        # BUY
        # ====================================================

        if unit_price <= float(max_price):

            ba.screenmessage(
                'BUY {} x{}'.format(
                    item_code,
                    amount,
                ),
                color=(0.2, 1.0, 0.2),
            )

            token = self._request_token

            self._waiting = False

            babase.apptimer(
                0.10,
                babase.Call(
                    self._send_amount,
                    sell_id,
                    amount,
                    token,
                ),
            )

            return

        # ====================================================
        # CANCEL IMMEDIATELY
        # ====================================================

        ba.screenmessage(
            'CANCEL NOW: {} > {}'.format(
                _format_price(unit_price),
                _format_price(max_price),
            ),
            color=(1.0, 0.3, 0.2),
        )

        print(
            'AUTOBUY CANCEL NOW:',
            sell_id,
            'UNIT:',
            unit_price,
            'MAX:',
            max_price,
        )

        self._waiting = False

        try:

            ba.chatmessage(
                CANCEL_COMMAND
            )

            ba.screenmessage(
                'CANCEL SENT',
                color=(1.0, 0.2, 0.2),
            )

            print(
                'AUTOBUY CANCEL SENT:',
                CANCEL_COMMAND,
            )

        except Exception as exc:

            print(
                'AUTOBUY CANCEL ERROR:',
                repr(exc),
            )

        self._finish_request()

    # ========================================================
    # SEND BUY AMOUNT
    # ========================================================

    def _send_amount(
        self,
        sell_id,
        amount,
        token,
    ):

        if not AUTO_BUY_ENABLED:
            return

        if self._pending_id != sell_id:
            return

        try:

            ba.chatmessage(
                str(amount)
            )

            ba.screenmessage(
                'BUY SENT: {} x{}'.format(
                    sell_id,
                    amount,
                ),
                color=(0.2, 1.0, 0.2),
            )

            print(
                'AUTOBUY BUY SENT:',
                sell_id,
                'AMOUNT:',
                amount,
            )

        except Exception as exc:

            print(
                'AUTOBUY BUY ERROR:',
                repr(exc),
            )

        self._finish_request()

    # ========================================================
    # FINISH
    # ========================================================

    def _finish_request(self):

        self._waiting = False

        self._pending_id = None

        self._request_token += 1

        babase.apptimer(
            0.05,
            babase.Call(
                self._process_next
            ),
        )