import os
import json


class State:
    def __init__(self, state_dir=".state"):
        self.state_dir = state_dir
        os.makedirs(self.state_dir, exist_ok=True)

        self.geo_file = os.path.join(state_dir, "geo.json")
        self.telegram_file = os.path.join(state_dir, "telegram.json")

        self.geo = self._read(self.geo_file)
        self.telegram = self._read(self.telegram_file)

    def _read(self, path):
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def save(self):
        with open(self.geo_file, "w", encoding="utf-8") as f:
            json.dump(self.geo, f, indent=2)

        with open(self.telegram_file, "w", encoding="utf-8") as f:
            json.dump(self.telegram, f, indent=2)

    def get_tg_offset(self):
        return int(self.telegram.get("offset", 0))

    def set_tg_offset(self, offset):
        self.telegram["offset"] = int(offset)