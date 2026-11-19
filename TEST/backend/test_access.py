import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import access_control
import admin
import ai_service
from main import app


class AccessControlTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.data_file = root / "access-control.json"
        self.prompt_dir = root / "channels"
        self.instruction_dir = root / "instruction-pack"
        self.complete_guide = root / "complete-guide.md"
        self.prompt_dir.mkdir()
        self.instruction_dir.mkdir()
        self.data_file.write_text(json.dumps(access_control.DEFAULT_DATA), encoding="utf-8")
        (self.prompt_dir / "b2b.md").write_text("B2B brain", encoding="utf-8")
        (self.prompt_dir / "b2c.md").write_text("B2C brain", encoding="utf-8")
        self.complete_guide.write_text("Complete shared CX guide", encoding="utf-8")
        for module_id, metadata in access_control.INSTRUCTION_MODULES.items():
            if module_id != "CX_WRITING_COMPLETE_GUIDE":
                (self.instruction_dir / metadata["filename"]).write_text(f"{module_id} rules", encoding="utf-8")
        self.patches = [
            patch.object(access_control, "DATA_FILE", self.data_file),
            patch.object(access_control, "CHANNEL_PROMPT_DIR", self.prompt_dir),
            patch.object(admin, "CHANNEL_PROMPT_DIR", self.prompt_dir),
            patch.object(access_control, "INSTRUCTION_PACK_DIR", self.instruction_dir),
            patch.object(admin, "INSTRUCTION_PACK_DIR", self.instruction_dir),
            patch.object(access_control, "COMPLETE_CX_GUIDE_FILE", self.complete_guide),
        ]
        for item in self.patches:
            item.start()
        self.client = TestClient(app)

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def headers(self, email):
        return {"X-User-Email": email}

    def test_login_returns_role_and_allowed_channels(self):
        super_profile = self.client.post("/api/access/login", json={"email": "developer@eand.ae"}).json()
        user_profile = self.client.post("/api/access/login", json={"email": "mariam.k@eand.ae"}).json()
        self.assertEqual(super_profile["role"], "super_admin")
        self.assertEqual({item["id"] for item in super_profile["channels"]}, {"b2b", "b2c", "security"})
        self.assertEqual([item["id"] for item in user_profile["channels"]], ["b2b"])
        self.assertEqual(self.client.post("/api/access/login", json={"email": "unknown@eand.ae"}).status_code, 403)

    def test_super_admin_creates_channels_and_assigns_admins(self):
        response = self.client.post("/api/access/channels", json={"name": "Government"}, headers=self.headers("developer@eand.ae"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(list((self.prompt_dir / 'government').glob('*.md'))), 3)
        self.assertTrue((self.prompt_dir / 'government' / '01_SYSTEM_INSTRUCTIONS.md').exists())
        assignment = self.client.put("/api/access/assignments", json={"email": "gov.admin@eand.ae", "name": "Gov Admin", "role": "channel_admin", "channel_id": "government"}, headers=self.headers("developer@eand.ae"))
        self.assertEqual(assignment.status_code, 200)

    def test_channel_creation_and_deletion_are_super_admin_only(self):
        for email in ('b2b.admin@eand.ae', 'b2b.approver1@eand.ae', 'mariam.k@eand.ae'):
            self.assertEqual(self.client.post('/api/access/channels', json={'name': 'Forbidden'}, headers=self.headers(email)).status_code, 403)
            self.assertEqual(self.client.delete('/api/access/channels/b2b', headers=self.headers(email)).status_code, 403)
        super_headers = self.headers('developer@eand.ae')
        data = access_control.load_access_data()
        data['approval_batches'] = [{'id': 'historic', 'channel_id': 'b2b', 'status': 'approved'}]
        access_control.save_access_data(data)
        deleted = self.client.delete('/api/access/channels/b2b', headers=super_headers)
        self.assertEqual(deleted.status_code, 200)
        self.assertGreater(deleted.json()['disabled_accounts'], 0)
        fresh = self.client.get('/api/access/me', headers=super_headers).json()
        self.assertNotIn('b2b', [channel['id'] for channel in fresh['channels']])
        self.assertEqual(self.client.get('/api/output-options?team_channel=b2b', headers=super_headers).status_code, 404)
        self.assertEqual(self.client.get('/api/access/me', headers=self.headers('mariam.k@eand.ae')).status_code, 401)
        self.assertTrue((self.prompt_dir / 'b2b.md').exists())
        retained = access_control.load_access_data()
        self.assertEqual(retained['approval_batches'][0]['id'], 'historic')
        self.assertTrue(next(channel for channel in retained['channels'] if channel['id'] == 'b2b')['deleted_at'])
        self.assertTrue(any(event['action'] == 'Channel deleted' for event in retained['activity']))
        self.assertEqual(self.client.delete('/api/access/channels/b2b', headers=super_headers).status_code, 404)
        self.assertEqual(self.client.delete('/api/access/channels/missing', headers=super_headers).status_code, 404)

    def test_channel_admin_assigns_only_users_in_own_channel(self):
        allowed = self.client.put("/api/access/assignments", json={"email": "new@eand.ae", "name": "New User", "role": "user", "channel_id": "b2b"}, headers=self.headers("b2b.admin@eand.ae"))
        denied_channel = self.client.put("/api/access/assignments", json={"email": "new@eand.ae", "name": "New User", "role": "user", "channel_id": "b2c"}, headers=self.headers("b2b.admin@eand.ae"))
        denied_admin = self.client.put("/api/access/assignments", json={"email": "new@eand.ae", "name": "New User", "role": "channel_admin", "channel_id": "b2b"}, headers=self.headers("b2b.admin@eand.ae"))
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(denied_channel.status_code, 403)
        self.assertEqual(denied_admin.status_code, 403)

    def test_channel_prompt_access_is_scoped(self):
        response = self.client.get("/api/access/channels/b2b/prompt", headers=self.headers("b2b.admin@eand.ae"))
        self.assertEqual(response.json()["content"], "B2B brain")
        self.assertEqual(self.client.get("/api/access/channels/b2c/prompt", headers=self.headers("b2b.admin@eand.ae")).status_code, 403)
        updated = self.client.put("/api/access/channels/b2b/prompt", json={"content": "New B2B brain"}, headers=self.headers("b2b.admin@eand.ae"))
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(self.prompt_dir.joinpath("b2b.md").read_text(encoding="utf-8"), "New B2B brain")

    def test_switching_channel_replaces_the_model_brain(self):
        self.assertIn("Complete shared CX guide", ai_service.guidelines_for_text("Hello", "b2b"))
        self.assertIn("B2B brain", ai_service.guidelines_for_text("Hello", "b2b"))
        self.assertIn("00_MASTER_INSTRUCTIONS rules", ai_service.guidelines_for_text("Hello", "b2b"))
        self.assertNotIn("Complete shared CX guide", ai_service.guidelines_for_text("Hello", "b2c"))
        self.assertIn("B2C_SYSTEM rules", ai_service.guidelines_for_text("Hello", "b2c"))
        self.assertNotEqual(
            ai_service.build_task_prompt("Hello", team_channel="b2b"),
            ai_service.build_task_prompt("Hello", team_channel="b2c"),
        )

    def test_instruction_modules_are_visible_and_routed_by_content_type(self):
        response = self.client.get("/api/access/channels/b2b/instructions", headers=self.headers("b2b.admin@eand.ae"))
        self.assertEqual(response.status_code, 200)
        items = {item["id"]: item for item in response.json()["instructions"]}
        self.assertTrue(items["CX_WRITING_COMPLETE_GUIDE"]["active"])
        self.assertTrue(items["CX_WRITING_COMPLETE_GUIDE"]["always_active"])
        self.assertTrue(items["02_WEBSITE_CONTENT_INSTRUCTIONS"]["active"])
        self.assertTrue(items["01_BRAND_RULES"]["available"])
        self.assertTrue(items["01_BRAND_RULES"]["active"])
        self.assertIn("05_B2B_MESSAGING_EXAMPLES", items)
        self.assertNotIn("06_B2C_MESSAGING_EXAMPLES", items)

        website = access_control.instruction_text_for("b2b", "Website")
        paid_search = access_control.instruction_text_for("b2b", "Google Paid Search")
        self.assertIn("02_WEBSITE_CONTENT_INSTRUCTIONS rules", website)
        self.assertIn("03_WEBSITE_COMPONENT_SCHEMA rules", website)
        self.assertNotIn("04_GOOGLE_PAID_SEARCH_INSTRUCTIONS rules", website)
        self.assertIn("04_GOOGLE_PAID_SEARCH_INSTRUCTIONS rules", paid_search)
        self.assertNotIn("03_WEBSITE_COMPONENT_SCHEMA rules", paid_search)
        self.assertIn("01_BRAND_RULES rules", website)
        self.assertIn("05_B2B_MESSAGING_EXAMPLES rules", website)
        b2c = access_control.instruction_text_for("b2c", "Email")
        self.assertIn("B2C_SYSTEM rules", b2c)
        self.assertIn("B2C_TEMPLATES rules", b2c)
        self.assertNotIn("01_BRAND_RULES rules", b2c)
        self.assertNotIn("06_B2C_MESSAGING_EXAMPLES rules", b2c)
        self.assertNotIn("B2C_USER_GUIDE rules", b2c)
        self.assertNotIn("05_B2B_MESSAGING_EXAMPLES rules", b2c)

        denied_cross_channel = self.client.get(
            "/api/access/channels/b2b/instructions/06_B2C_MESSAGING_EXAMPLES",
            headers=self.headers("b2b.admin@eand.ae"),
        )
        self.assertEqual(denied_cross_channel.status_code, 404)

    def test_channel_admin_can_hide_unused_instructions(self):
        headers = self.headers("b2b.admin@eand.ae")
        toggled = self.client.put(
            "/api/access/channels/b2b/instructions/02_WEBSITE_CONTENT_INSTRUCTIONS",
            json={"active": False}, headers=headers,
        )
        edited = self.client.put(
            "/api/access/channels/b2b/instructions/02_WEBSITE_CONTENT_INSTRUCTIONS",
            json={"content": "Changed"}, headers=headers,
        )
        self.assertEqual(toggled.status_code, 200)
        self.assertFalse(toggled.json()["active"])
        self.assertEqual(edited.status_code, 404)
        listed = self.client.get('/api/access/channels/b2b/instructions', headers=headers).json()['instructions']
        self.assertNotIn('02_WEBSITE_CONTENT_INSTRUCTIONS', [item['id'] for item in listed])
        self.assertNotIn('README', [item['id'] for item in listed])

    def test_channel_admin_edits_are_isolated_and_used(self):
        url = '/api/access/channels/b2b/instructions/01_BRAND_RULES'
        response = self.client.put(url, json={'content': 'B2B custom brand rule'}, headers=self.headers('b2b.admin@eand.ae'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('B2B custom brand rule', access_control.instruction_text_for('b2b', 'Email'))
        self.assertNotIn('B2B custom brand rule', access_control.instruction_text_for('b2c', 'Email'))
        self.assertEqual((self.instruction_dir / '01_BRAND_RULES.md').read_text(), '01_BRAND_RULES rules')
        self.assertEqual(self.client.put(url, json={'content': 'Not allowed'}, headers=self.headers('b2c.admin@eand.ae')).status_code, 403)

    def test_ai_request_cannot_use_another_channel(self):
        response = self.client.post("/api/analyze", json={"generated": "Hello", "team_channel": "b2c"}, headers=self.headers("mariam.k@eand.ae"))
        self.assertEqual(response.status_code, 403)
        image_response = self.client.post("/api/generate", json={"prompt": "Poster", "teamChannel": "b2c"}, headers=self.headers("mariam.k@eand.ae"))
        self.assertEqual(image_response.status_code, 404)

    def test_workspace_permissions_are_returned_and_enforced(self):
        assigned = self.client.put(
            "/api/access/assignments",
            json={
                "email": "rewrite.only@eand.ae",
                "name": "Rewrite Only",
                "role": "user",
                "channel_id": "b2b",
                "workspaces": ["rewrite"],
            },
            headers=self.headers("b2b.admin@eand.ae"),
        )
        self.assertEqual(assigned.status_code, 200)
        self.assertEqual(self.client.post("/api/access/login", json={"email": "rewrite.only@eand.ae", "password": "111111"}).status_code, 403)
        profile = self.client.get('/api/access/me', headers=self.headers('rewrite.only@eand.ae')).json()
        self.assertEqual(profile["workspaces"], ["rewrite"])
        denied = self.client.post(
            "/api/generate",
            json={"prompt": "Poster", "teamChannel": "b2b"},
            headers=self.headers("rewrite.only@eand.ae"),
        )
        self.assertEqual(denied.status_code, 404)

    def test_assignment_requires_at_least_one_workspace(self):
        response = self.client.put(
            "/api/access/assignments",
            json={"email": "none@eand.ae", "name": "No Access", "role": "user", "channel_id": "b2b", "workspaces": []},
            headers=self.headers("b2b.admin@eand.ae"),
        )
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
