# Augmintech blog pipeline — handoff for Claude

Read this fully before doing anything. You are continuing an automated workflow that turns client blog HTML files into Elementor drafts on augmintech.com (WordPress + Elementor + Rank Math, Hostinger).

## How Ashish wants you to work
- Reply in **short bullet points**. No long paragraphs.
- Give **one best way**, not options. Don't switch approach mid-way; if something fails, fix the same approach first.
- Say upfront if you're unsure something will work. Verify before reporting.
- Never publish. Only create **drafts**. Ashish publishes.
- Never paste large files, base64 images or full HTML into the chat. Files move: his Mac folder → your container → GitHub → WordPress.
- Don't flag redirected slugs. Send only the files he asks for.

## Setup this workflow depends on
| Piece | Where |
|---|---|
| WordPress connector | Custom connector `augmintech`, URL `https://augmintech.com/wp-json/mcp/mcp-oauth-server` (OAuth as a WP admin) |
| Custom abilities | Code Snippets plugin, snippet **#49 "Augmintech blog abilities"** (edit at `wp-admin/admin.php?page=edit-snippet&id=49` via the built-in browser pane; Claude in Chrome can't open wp-admin) |
| Asset repo | `ashisheverclif/augmintech-blog-assets` (public). WordPress pulls images/HTML from `raw.githubusercontent.com/...` at a commit SHA |
| Input folder | `/Users/ashish/Desktop/Augmintech Blogs` on his Mac (connect it via the desktop app). Holds client HTML files, WhatsApp banner files and the sheet (`blogs.numbers` or `blogs.xlsx`) |
| Build script | `tools/build_blog.py` in this repo (+ `tools/examples/*.json` configs) |
| Log of finished rows | `tools/done.csv` — append a row after every draft |

Network notes: the cloud container can reach GitHub but **not** augmintech.com (proxy 403). The device shell on his Mac also can't reach augmintech.com. Only the MCP connector and the browser pane talk to the site.

### Abilities (call with `mcp-adapter-execute-ability`)
- `augmintech/upload-image` — `{filename, source_url (raw GitHub URL), alt, title}` → returns `{id, url, bytes, md5}`. Always compare md5 with your local file.
- `augmintech/create-blog-draft` — `{title (=H1), slug, html_url (must be in this repo), course_url, categories:[names], featured_media (attachment id), seo_title, seo_description, focus_keyword, author_login (default Augmintech), post_id (only to update an existing draft)}`. It clones Elementor template post **73340** and fills: H1 widget `44f16e9`, blog HTML widget `8c76ed1`, bottom CTA `b81704a` (its /courses/ links → course_url), sidebar "Get Course" button `f43012d` → course_url. Returns `html_md5` — compare with your file.
- `augmintech/get-elementor-layout` — `{post_id}` read-only check.

## Trigger: "upload blogs.xlsx"
1. **Read the sheet** in his folder (Numbers files: `pip install numbers-parser` in the device shell, read `sheets[0].tables[0]`). Columns: `html_file, slug, course_url, banner_file, categories, seo_title, meta_description, featured_image`. Rows 1–2 are header/legend, row 3 is the example.
2. **Skip rows already in `tools/done.csv`.** Process only new rows.
3. **Fix sheet mistakes silently, then report them:** slugs with spaces → hyphens; if `categories` contains a banner filename, pick the right category (Piping Design, MEP, HVAC, BIM Software…). If course_url/banner clearly don't match the blog (e.g. blog's own CTA sells BIM MEP but row says Piping), **ask him** with one AskUserQuestion before building.
4. **Stage files** (`device_stage_files`) → they land in `/mnt/user-data/uploads/Augmintech Blogs/`. Never print them.
5. **Inspect with short summaries only** (headings with word-% position, image count/alts, WhatsApp links, CTA text, editor notes, course links). See the analysis snippets pattern: print positions, not content.
6. **Write a config** like `tools/examples/c84.json` and run `python3 tools/build_blog.py config.json`. The script:
   - scopes all CSS to `#aug-<slug>`, removes `@import` fonts (fonts inherit), progress bar + its script, eyebrow, the hero `<h1>` (its text becomes the Elementor H1 / post title) and the meta pills, editor-note comments;
   - converts every data-URI image to WebP q65 (max 1200 px; SVGs rendered to WebP via Playwright) named `<prefix>-<first-5-alt-words>.webp`, leaves `__IMGn__` placeholders;
   - inserts the banner before `banner_before` (strip `&amp;utm_source=chatgpt.com`);
   - applies `replace` pairs (remove WhatsApp buttons, retitle/remove WhatsApp-offer CTAs and sentences);
   - adds internal links from `links` = `[exact context text, anchor, target-slug]`;
   - forces every `/courses/` link to `course_url` and reports changed ones; asserts no data URIs/progress left and tags balanced.
7. **Push images** to `blogs/<nn>-<slug>/` and commit → upload each with `upload-image` using the raw URL at that commit SHA → check md5.
8. **Replace placeholders** with the returned URLs (uploads go to `/wp-content/uploads/YYYY/MM/<filename>`; use the URL the tool returns, it may add `-1`), push the HTML, then `create-blog-draft` with `html_url` at the new SHA. Featured image = first image unless the sheet says otherwise.
9. **Verify in the browser pane** (`?p=<id>&preview=true`): every image HEAD 200, H1 correct, banner present, exactly 1 `wa.me` link (the banner's), all `/courses/` links = course_url, internal link count, interactive widgets still work.
10. **Append to `tools/done.csv`**, commit, and report per blog: edit + preview links, banner position, internal links, removed items, SEO title/description/keyword, anything to check.

## Editorial rules (from Ashish)
- **Banner:** ~25–30% into the post (by word count; ignore long tables inside scroll boxes), directly **above a heading**. Use the banner file from the sheet.
- **WhatsApp:** remove every WhatsApp link/button from the client HTML; the banner's WhatsApp link is the only one. If a CTA box only offered something "on WhatsApp", remove the box (or retitle it as a course CTA if it also promotes the course) and remove sentences promising that freebie.
- **First heading:** the client's top heading (hero H1, older drafts used first H2) is removed from the HTML and used as the Elementor H1.
- **Course links:** all course links, sidebar CTA and bottom CTA → `course_url`. Tell him if any client link was different.
- **Internal links:** 2–7 per post, anchor ≤4–5 words, in body paragraphs/lists (not headings), only to **published** posts (see `tools/published_posts_2026-10-19.json`; refresh from `https://augmintech.com/post-sitemap.xml` via WebFetch). Don't link to unpublished drafts (team publishes sometimes one by one, sometimes in batches, so a draft link could 404). On "refresh links" / "published X": re-read the sitemap and rebuild remaining drafts (`create-blog-draft` with `post_id`) to add links to newly live posts. Published posts can't be edited by the tool. Follow any client editor note asking for a specific link (e.g. "see our ... guide").
- **Featured image:** first image, but skip software logos (pick the first real picture).
- **Sheet quirks:** `html_file` names may not match the folder; match by number prefix and report it. Build check only flags the progress *bar* (`id="progress"`), not the word.
- **SEO (Rank Math):** if blank in the sheet, write them: title ≤60 chars with the focus keyword first, description 140–160 chars, focus keyword = slug words.
- **Author:** Augmintech. **Theme:** h2 28px #1a1a1a, links #0F4C81 (hover #18d104), CTA boxes #1a1a1a with green button (already in build_blog.py).
- **No large data URIs** in anything sent to WordPress.

## Open items (as of 2026-11-10 evening)
- 81–95 are published. Drafts 96–110 (73659–73673, cross-linked to each other) and 111–119 (73713–73721, cross-linked) await publish; each batch is meant to be published together. Once 96–110 are live, 111–119 can get links to them (e.g. 118 says "see our interior design interview questions guide" = 110).
- Linking from published posts (e.g. 83 → 81/82, older posts → 85–110) needs snippet #49 changed to allow updating published posts; ask Ashish first.
- 89 fire-fighting-system: "Full guide" labels for hydrant/sprinkler are plain text; 86/87 are live now, so they could be linked (needs the snippet change, since 89 is published). "Wet riser / Fire pump (coming soon)" labels are still on the live post.
- 100, 102–105 use software logos and vendor/third-party screenshots and renders (Autodesk, Chaos/V-Ray, D5, Vu Nguyen render reused in 104). Check rights before publishing.
- Bottom CTA text comes from template 73340 (MEP Career Program); only its link is swapped. Ask whether he wants per-course CTA banners.
- Test draft 73420 should be deleted (tools can't delete).
