from supabase import create_client, Client


class SupabaseClient:
    def __init__(self, url: str, key: str):
        self.client: Client = create_client(url, key)

    def sync_phrases(self, phrases: list) -> None:
        """Upsert phrases from config — inserts new ones, updates name/phrase text,
        preserves counts — and deletes any phrase no longer present in config."""
        for p in phrases:
            self.client.table("phrases").upsert(
                {
                    "id": p["id"],
                    "name": p["name"],
                    "phrase": p["phrase"],
                    "description": p.get("description", ""),
                },
                on_conflict="id",
            ).execute()

        current_ids = [p["id"] for p in phrases]
        self.client.table("phrases").delete().not_.in_("id", current_ids).execute()

    def increment(self, phrase_id: str) -> int:
        result = self.client.rpc("increment_phrase_count", {"phrase_id": phrase_id}).execute()
        return result.data
