#nexus_scraper.py

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time
import sqlite3

# Setup headless Chrome
options = Options()
options.add_argument("--headless")
driver = webdriver.Chrome(options=options)

# SQLite setup
conn = sqlite3.connect("nexus_commands.db")
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS commands (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        syntax TEXT,
        description TEXT,
        mode TEXT,
        url TEXT
    )
""")

# Load index page
index_url = "https://www.cisco.com/c/en/us/td/docs/switches/datacenter/nexus9000/sw/93x/command/reference/config/b_N9K_Config_Commands_93x.html"
driver.get(index_url)
time.sleep(5)

# Extract all command links
links = driver.find_elements(By.CSS_SELECTOR, "a[href*='command/reference/config/']")
command_urls = [link.get_attribute("href") for link in links if "command" in link.text.lower()]

print(f"Found {len(command_urls)} command pages.")

# Visit each command page
for url in command_urls:
    try:
        driver.get(url)
        time.sleep(3)

        name = driver.find_element(By.TAG_NAME, "h1").text.strip()
        syntax = ""
        description = ""
        mode = ""

        # Try to extract sections
        sections = driver.find_elements(By.TAG_NAME, "p")
        for section in sections:
            text = section.text.lower()
            if "syntax" in text:
                syntax = section.text.strip()
            elif "description" in text:
                description = section.text.strip()
            elif "command mode" in text:
                mode = section.text.strip()

        cursor.execute("""
            INSERT INTO commands (name, syntax, description, mode, url)
            VALUES (?, ?, ?, ?, ?)
        """, (name, syntax, description, mode, url))
        conn.commit()
        print(f"Stored: {name}")
    except Exception as e:
        print(f"Failed to process {url}: {e}")

driver.quit()
conn.close()
