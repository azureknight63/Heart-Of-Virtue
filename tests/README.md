# Test Organization Documentation Index

Welcome! The Heart-Of-Virtue test suite has been organized hierarchically. Start here to understand the new structure.

## 📚 Documentation Files

### 1. **[TEST_ORGANIZATION.md](./TEST_ORGANIZATION.md)** - Comprehensive Guide
The complete reference with:
- Organization strategy explanation
- All 12 test categories with full file listings
- How to run tests by category
- Import compatibility details
- Benefits and design rationale

**Start here if:** You want to understand the full system

### 2. **[ORGANIZATION_QUICK_REFERENCE.md](./ORGANIZATION_QUICK_REFERENCE.md)** - Quick Lookup
Fast reference with:
- Test categories at a glance
- Quick run commands
- Pattern matching guide
- Troubleshooting tips

**Start here if:** You want quick commands and patterns

### 3. **[FILES_BY_CATEGORY.md](./FILES_BY_CATEGORY.md)** - Visual File List
All 64+ test files organized visually by category with:
- File names with descriptions
- Quick run commands for each category
- Search guide for finding tests
- Statistics and links

**Start here if:** You prefer a visual/list format

---

## 🗂️ Test Categories

| Category | Files | Quick Run |
|----------|-------|-----------|
| Combat | 7 | `pytest tests/ -k "combat or move"` |
| Config | 7 | `pytest tests/ -k "config"` |
| Functions | 4 | `pytest tests/ -k "functions"` |
| Game Mechanics | 6 | `pytest tests/ -k "game or state"` |
| Items | 5 | `pytest tests/ -k "loot or commodity"` |
| Maps | 7 | `pytest tests/ -k "map or tile"` |
| Miscellaneous | 6 | `pytest tests/test_animations.py [...]` |
| NPC/AI | 9 | `pytest tests/ -k "merchant or mynx"` |
| Positions | 3 | `pytest tests/ -k "positions"` |
| UI | 5 | `pytest tests/ -k "shop_ui or interface"` |
| Manual | 3 | `python tests/manual_*.py` |
| UAT | 3 | `python tests/uat/run_uat_memory.py` |

---

## ⚡ Common Tasks

### Run All Tests
```bash
cd c:\Users\azure\PycharmProjects\Heart-Of-Virtue
pytest tests/
```

### Run Combat Tests
```bash
pytest tests/ -k "combat or move or advance or bat" -v
```

### Run Merchant/Shop Tests
```bash
pytest tests/ -k "merchant or shop" -v
```

### Run with Coverage
```bash
pytest tests/ --cov=src --cov=ai --cov-report=term-missing
```

### Find Tests About [Something]
See **FILES_BY_CATEGORY.md** → "File Search Guide" table

---

## 📊 Quick Stats

- **64 test files** organized in root `tests/` directory
- **781 test cases** total
- **12 logical categories** 
- **~20 seconds** execution time
- **100% pass rate** (4 skipped)

---

## ✅ Organization Method

Rather than physical subdirectories (which break imports), we use:

1. **Naming Conventions** - File names follow category patterns
2. **Pytest Markers** - Use `-k` flag to run related tests
3. **Documentation** - Clear guides and references
4. **Comments** - Test files indicate their category

**Benefits:**
- Clear logical grouping
- Easy test discovery
- Full import compatibility
- No breaking changes
- Scales naturally

---

## 🔧 Configuration Files

- **`conftest.py`** - Pytest configuration with module shims (unchanged)
- **All test files** - Remain in `tests/` root for import consistency

---

## 📖 How to Use These Docs

### If you're...

**🆕 New to the project**
1. Read this file (you're reading it!)
2. Check `ORGANIZATION_QUICK_REFERENCE.md` for commands
3. Use `FILES_BY_CATEGORY.md` to find specific tests

**🐛 Debugging a feature**
1. Find your feature in the category table above
2. Use the "Quick Run" command to run related tests
3. Check `FILES_BY_CATEGORY.md` for exact file names

**📝 Adding a new test**
1. Read `TEST_ORGANIZATION.md` → "Adding New Tests"
2. Choose the appropriate category
3. Name your file following the pattern
4. Place in `tests/` root directory
5. Run with category pattern: `pytest tests/ -k "your_pattern"`

**🔍 Looking for a specific test**
1. Search the file name in `FILES_BY_CATEGORY.md`
2. Or use `pytest --collect-only` to list all tests
3. Or grep: `grep -r "test_name" tests/`

---

## 🎯 Next Steps

1. **Pick a documentation file** based on your need (above)
2. **Run a test** to verify setup works: `pytest tests/ -k "combat" -v`
3. **Bookmark** the quick reference for easy access

---

## 📞 Questions?

- **How do I...** - Check `ORGANIZATION_QUICK_REFERENCE.md`
- **Which file tests...** - Check `FILES_BY_CATEGORY.md`
- **Why is it organized this way...** - Check `TEST_ORGANIZATION.md`

---

**Organization Complete:** November 1, 2025  
**Status:** ✅ All 781 tests passing  
**Ready for:** Development, CI/CD integration, team onboarding

