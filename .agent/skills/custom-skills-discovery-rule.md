# Custom Skills Discovery & Environment Rule

This skill defines the rules for skill discovery and modification in the Antigravity environment.

## Environment Constraints
- **Core Installation Path (`/`)**: This path is strictly read-only and reserved for Google. Never assume you can write, add, or modify skills in `/` or internal system directories.
- **Official Custom Skills Locations**:
  - **Global Skills**: `~/.gemini/antigravity/skills/` (mapped to `C:\Users\ROG\.gemini\antigravity\skills/` on this machine)
  - **Workspace Skills**: `.agent/skills/` in the root of the project (`d:\code_xI\Translator_Web\.agent\skills/`)

## Guidelines for Skill Discovery
1. When looking for custom/user skills, only search and discover skills within the two official paths:
   - `~/.gemini/antigravity/skills/`
   - `.agent/skills/`
2. Do NOT say "skills can only be installed by Google". The user has full permission and ability to install and modify skills in these two designated folders.
3. If the user asks you to add, modify, or create a skill:
   - For global scope: write to `~/.gemini/antigravity/skills/`
   - For workspace/project scope: write to `.agent/skills/`
