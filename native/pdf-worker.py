"""Trusted offline PDF printing with the bundled POSIX browser and its driver."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'runtime/tools/documents'))


def main():
    from playwright.sync_api import sync_playwright
    source,target,executable=(Path(value).resolve() for value in sys.argv[1:4])
    with sync_playwright() as runtime:
        browser=runtime.chromium.launch(executable_path=str(executable),headless=True,chromium_sandbox=True,args=['--disable-gpu'])
        try:
            context=browser.new_context(offline=True,viewport={'width':1280,'height':960})
            page=context.new_page()
            page.goto(source.as_uri(),wait_until='load',timeout=60000)
            page.evaluate('document.fonts.ready')
            page.pdf(path=str(target),print_background=True,prefer_css_page_size=True)
        finally:browser.close()


if __name__=='__main__':main()
