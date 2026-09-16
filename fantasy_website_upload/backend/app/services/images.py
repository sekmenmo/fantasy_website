from __future__ import annotations


AVATAR_FULL_URL = "https://sleepercdn.com/avatars/{avatar_id}"
AVATAR_THUMB_URL = "https://sleepercdn.com/avatars/thumbs/{avatar_id}"
PLAYER_HEADSHOT_URL = "https://sleepercdn.com/content/nfl/players/{player_id}.jpg"


def avatar_url(avatar_id: str | None, *, thumbnail: bool = False) -> str | None:
    if not avatar_id:
        return None
    template = AVATAR_THUMB_URL if thumbnail else AVATAR_FULL_URL
    return template.format(avatar_id=avatar_id)


class PlayerImageProvider:
    def get_image_url(self, player_id: str, nfl_team: str | None = None) -> str | None:
        if not player_id or player_id == "0":
            return None
        return PLAYER_HEADSHOT_URL.format(player_id=player_id)
