import asyncio
from playwright.async_api import async_playwright
import json

async def drive_app():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        findings = {}
        
        # 1. Home page - check everything
        await page.goto("http://localhost:3003")
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(1000)
        
        body = await page.inner_text("body")
        html = await page.inner_html("body")
        
        # Check all button labels
        buttons = await page.query_selector_all("button")
        btn_texts = []
        for btn in buttons:
            text = (await btn.inner_text()).strip()
            if text:
                btn_texts.append(text)
        findings["home_buttons"] = btn_texts[:30]
        
        # 2. Navigate to Dashboard and test ALL tabs
        await page.goto("http://localhost:3003")
        await page.wait_for_timeout(1000)
        
        # Click Dashboard button
        for btn in await page.query_selector_all("button"):
            text = (await btn.inner_text()).strip().lower()
            if "dash" in text and len(text) < 15:
                await btn.click()
                await page.wait_for_timeout(1500)
                break
        
        body = await page.inner_text("body")
        html = await page.inner_html("body")
        
        # Check dashboard content
        findings["dashboard"] = {
            "content_length": len(body),
            "has_graph_element": "graph" in body.lower() or "d3" in html.lower() or "svg" in html.lower(),
            "has_telemetry": "telemetry" in body.lower() or "gpu" in body.lower() or "cpu" in body.lower(),
            "has_routing": "router" in body.lower() or "model" in body.lower(),
            "has_axioms": "axiom" in body.lower(),
            "has_memory": "memory" in body.lower() or "redis" in body.lower() or "postgres" in body.lower(),
            "has_skills": "skill" in body.lower(),
            "has_config": "config" in body.lower(),
            "has_keys": "key" in body.lower() or "api" in body.lower(),
            "has_mcp": "mcp" in body.lower(),
            "has_hooks": "hook" in body.lower(),
            "has_logs": "log" in body.lower(),
            "has_scheduling": "schedul" in body.lower(),
        }
        
        # Click each tab and check for errors
        tab_results = {}
        for btn in await page.query_selector_all("button"):
            text = (await btn.inner_text()).strip()
            if text and len(text) < 25 and text.lower() not in ["chat", "dash"]:
                try:
                    await btn.click()
                    await page.wait_for_timeout(800)
                    body = await page.inner_text("body")
                    tab_results[text] = {
                        "content_length": len(body),
                        "has_data": len(body) > 50,
                    }
                except Exception as e:
                    tab_results[text] = {"error": str(e)[:100]}
        findings["tab_results"] = tab_results
        
        # 3. Test Scheduling panel
        for btn in await page.query_selector_all("button"):
            text = (await btn.inner_text()).strip().lower()
            if "schedul" in text:
                await btn.click()
                await page.wait_for_timeout(1000)
                body = await page.inner_text("body")
                findings["scheduling"] = {
                    "has_content": len(body) > 50,
                    "has_create_btn": "+ new" in body.lower() or "new schedul" in body.lower(),
                    "has_tasks": "daily" in body.lower() or "backup" in body.lower() or "schedule" in body.lower(),
                }
                break
        
        # 4. Test Settings panel
        for btn in await page.query_selector_all("button"):
            text = (await btn.inner_text()).strip().lower()
            if "settings" in text or "preference" in text:
                await btn.click()
                await page.wait_for_timeout(1000)
                body = await page.inner_text("body")
                findings["settings"] = {
                    "has_content": len(body) > 50,
                    "has_models": "model" in body.lower(),
                    "has_appearance": "appearance" in body.lower() or "font" in body.lower(),
                }
                break
        
        # 5. Test Sidebar
        await page.goto("http://localhost:3003")
        await page.wait_for_timeout(1000)
        
        aside = await page.query_selector("aside")
        if aside:
            sidebar_html = await aside.inner_html()
            findings["sidebar"] = {
                "has_create": "new session" in sidebar_html.lower(),
                "has_search": "search" in sidebar_html.lower(),
                "has_archive": "archive" in sidebar_html.lower(),
                "has_theme": "theme" in sidebar_html.lower(),
            }
        
        # 6. Test Composer
        main = await page.query_selector("main")
        if main:
            main_html = await main.inner_html()
            findings["composer"] = {
                "has_textarea": "textarea" in main_html,
                "has_upload": "attach" in main_html.lower(),
                "has_send": "send" in main_html.lower(),
            }
        
        # 7. CSS polish
        findings["css_polish"] = {
            "has_glassmorphism": "backdrop" in html.lower() or "blur" in html.lower(),
            "has_gradients": "gradient" in html.lower() or "bg-gradient" in html.lower(),
            "has_animations": "animation" in html.lower() or "@keyframes" in html or "animate" in html.lower(),
            "has_transitions": "transition" in html.lower(),
        }
        
        print(json.dumps(findings, indent=2, default=str))
        await browser.close()

asyncio.run(drive_app())