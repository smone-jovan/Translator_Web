@echo off
echo Copying agent-skills...
xcopy "C:\Users\ROG\.gemini\antigravity-ide\knowledge\agent-skills\artifacts\.claude\skills" "C:\Users\ROG\.gemini\antigravity\skills" /E /I /Y

echo Copying mattpocock-skills...
xcopy "C:\Users\ROG\.gemini\antigravity-ide\knowledge\mattpocock-skills\artifacts\.claude\skills" "C:\Users\ROG\.gemini\antigravity\skills" /E /I /Y

echo Copying ui-ux-pro-max skills...
xcopy "C:\Users\ROG\.gemini\antigravity-ide\knowledge\ui-ux-pro-max\artifacts\.claude\skills" "C:\Users\ROG\.gemini\antigravity\skills" /E /I /Y

echo Creating humanizer skill...
mkdir "C:\Users\ROG\.gemini\antigravity\skills\humanizer" 2>nul
echo --- > "C:\Users\ROG\.gemini\antigravity\skills\humanizer\SKILL.md"
echo name: humanizer >> "C:\Users\ROG\.gemini\antigravity\skills\humanizer\SKILL.md"
echo description: Detect and remove 29 AI writing patterns to make text sound natural and human-like. >> "C:\Users\ROG\.gemini\antigravity\skills\humanizer\SKILL.md"
echo --- >> "C:\Users\ROG\.gemini\antigravity\skills\humanizer\SKILL.md"
type "C:\Users\ROG\.gemini\antigravity-ide\knowledge\humanizer-skill\artifacts\humanizer-guide.md" >> "C:\Users\ROG\.gemini\antigravity\skills\humanizer\SKILL.md"

echo Creating superpowers-workflow skill...
mkdir "C:\Users\ROG\.gemini\antigravity\skills\superpowers-workflow" 2>nul
echo --- > "C:\Users\ROG\.gemini\antigravity\skills\superpowers-workflow\SKILL.md"
echo name: superpowers-workflow >> "C:\Users\ROG\.gemini\antigravity\skills\superpowers-workflow\SKILL.md"
echo description: Software development workflow including brainstorming, plan writing, TDD, and debugging. >> "C:\Users\ROG\.gemini\antigravity\skills\superpowers-workflow\SKILL.md"
echo --- >> "C:\Users\ROG\.gemini\antigravity\skills\superpowers-workflow\SKILL.md"
type "C:\Users\ROG\.gemini\antigravity-ide\knowledge\superpowers-workflow\artifacts\superpowers-guide.md" >> "C:\Users\ROG\.gemini\antigravity\skills\superpowers-workflow\SKILL.md"

echo All skills copied successfully!
