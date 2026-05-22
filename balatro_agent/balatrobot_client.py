from __future__ import annotations
import time
import requests


ENDPOINT = "http://127.0.0.1:12346"

INVALID_STATE = -32000
BAD_REQUEST = -32001
NOT_ALLOWED = -32002
INTERNAL_ERROR = -32003


class BalatrobotError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(f"BalatrobotError {code}: {message}")
        self.code = code
        self.message = message


class BalatrobotClient:
    def __init__(self, endpoint: str = ENDPOINT, timeout: float = 30.0):
        self.endpoint = endpoint
        self.timeout = timeout
        self._id = 0

    def _post(self, method: str, params: dict | None = None) -> dict:
        self._id += 1
        payload = {"jsonrpc": "2.0", "method": method, "id": self._id}
        if params is not None:
            payload["params"] = params
        resp = requests.post(self.endpoint, json=payload, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def _rpc(self, method: str, params: dict | None = None) -> dict:
        attempts = 0
        last_err: BalatrobotError | None = None
        while attempts < 3:
            try:
                data = self._post(method, params)
            except requests.RequestException as e:
                attempts += 1
                last_err = BalatrobotError(INTERNAL_ERROR, str(e))
                time.sleep(1.0)
                continue

            if "error" in data and data["error"]:
                code = data["error"].get("code", INTERNAL_ERROR)
                msg = data["error"].get("message", "unknown")
                err = BalatrobotError(code, msg)
                if code in (INVALID_STATE, NOT_ALLOWED):
                    # Re-read state and retry once
                    if method != "gamestate":
                        self._post("gamestate")
                    attempts += 1
                    last_err = err
                    time.sleep(0.3)
                    continue
                if code == INTERNAL_ERROR:
                    attempts += 1
                    last_err = err
                    time.sleep(1.0)
                    continue
                if code == BAD_REQUEST:
                    # Log and return current gamestate so caller can fallback
                    print(f"[balatrobot] BAD_REQUEST on {method}({params}): {msg}")
                    gs = self._post("gamestate")
                    return gs.get("result", {})
                raise err

            return data.get("result", {})

        raise last_err or BalatrobotError(INTERNAL_ERROR, f"{method} failed after retries")

    def get_gamestate(self) -> dict:
        return self._rpc("gamestate")

    def menu(self) -> None:
        """Navigate back to the main menu before starting a new run."""
        for attempt in range(4):
            try:
                self._rpc("menu")
                time.sleep(0.8)
                return
            except Exception:
                time.sleep(1.5)

    def start(self, deck: str, stake: str, seed: str | None = None) -> dict:
        self.menu()
        params: dict = {"deck": deck, "stake": stake}
        if seed:
            params["seed"] = seed
        return self._rpc("start", params)

    def select(self) -> dict:
        return self._rpc("select", {})

    def skip(self) -> dict:
        return self._rpc("skip", {})

    def play(self, cards: list[int]) -> dict:
        return self._rpc("play", {"cards": cards})

    def discard(self, cards: list[int]) -> dict:
        return self._rpc("discard", {"cards": cards})

    def buy(self, card: int | None = None, voucher: int | None = None,
            pack: int | None = None) -> dict:
        params: dict = {}
        if card is not None:
            params["card"] = card
        elif voucher is not None:
            params["voucher"] = voucher
        elif pack is not None:
            params["pack"] = pack
        return self._rpc("buy", params)

    def sell(self, joker: int | None = None, consumable: int | None = None) -> dict:
        params: dict = {}
        if joker is not None:
            params["joker"] = joker
        elif consumable is not None:
            params["consumable"] = consumable
        return self._rpc("sell", params)

    def reroll(self) -> dict:
        return self._rpc("reroll", {})

    def use(self, consumable: int, cards: list[int] | None = None) -> dict:
        params: dict = {"consumable": consumable}
        if cards:
            params["cards"] = cards
        return self._rpc("use", params)

    def pack(self, card: int | None = None, targets: list[int] | None = None,
             skip: bool = False) -> dict:
        params: dict = {}
        if skip:
            params["skip"] = True
        else:
            if card is not None:
                params["card"] = card
            if targets:
                params["targets"] = targets
        return self._rpc("pack", params)

    def cash_out(self) -> dict:
        return self._rpc("cash_out", {})

    def next_round(self) -> dict:
        return self._rpc("next_round", {})
