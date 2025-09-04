import pandas as pd
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time
import os

chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument('--no-sandbox')
chrome_options.add_argument('--disable-dev-shm-usage')
chrome_options.binary_location = '/usr/bin/chromium-browser'
driver = webdriver.Chrome(options=chrome_options)

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
MAX_DEPTH = 2
pdf_links = []
input_csv = "college_links_checked.csv"
output_csv = "faculty_emails_advanced.csv"
pdf_output_csv = "pdf_links_to_extract.csv"

def commit_progress(college_name):
    print(f"\n--- Saving progress for {college_name} ---")
    os.system(f"git add {input_csv} {output_csv} {pdf_output_csv}")
    commit_message = f"Progress: Scraped data for {college_name}"
    os.system(f"git commit -m '{commit_message}' || true")
    print("Pushing updates to GitHub...")
    os.system("git push")
    print("--- Progress saved successfully! ---\n")

def extract_faculty_info(html):
    soup = BeautifulSoup(html, "html.parser")
    faculty = []
    for table in soup.find_all('table'):
        rows = table.find_all('tr')
        for row in rows:
            cols = row.find_all(['td', 'th'])
            text_cols = [c.get_text(separator=" ", strip=True) for c in cols]
            emails = set()
            for text in text_cols:
                emails.update(EMAIL_REGEX.findall(text))
            for email in emails:
                name = ''
                dep = ''
                for col in text_cols:
                    if email in col:
                        continue
                    if not name and len(col) <= 80:
                        name = col
                    elif not dep:
                        dep = col
                faculty.append({"Name": name, "Department": dep, "Email": email})
    for ul in soup.find_all('ul'):
        for li in ul.find_all('li'):
            text = li.get_text(separator=" ", strip=True)
            emails = EMAIL_REGEX.findall(text)
            for email in emails:
                rest = text.replace(email, '').strip('-, ')
                faculty.append({"Name": rest, "Department": '', "Email": email})
    for div in soup.find_all('div'):
        text = div.get_text(separator=" ", strip=True)
        emails = EMAIL_REGEX.findall(text)
        for email in emails:
            rest = text.replace(email, '').strip('-, ')
            faculty.append({"Name": rest, "Department": '', "Email": email})
    for a in soup.find_all('a', href=True):
        if a['href'].startswith("mailto:"):
            email = a['href'].replace('mailto:', '').split('?')[0]
            name = a.get_text(strip=True)
            faculty.append({"Name": name, "Department": '', "Email": email})
    for email in EMAIL_REGEX.findall(html):
        faculty.append({"Name": '', "Department": '', "Email": email})
    return faculty

def crawl(url, depth, root_url, visited, college):
    if depth > MAX_DEPTH or url in visited or not url.startswith(('http', 'https')):
        return []
    visited.add(url)
    try:
        driver.get(url)
        time.sleep(2)
        html = driver.page_source
        staff = extract_faculty_info(html)
        substaff = []
        soup = BeautifulSoup(html, 'html.parser')
        for a in soup.find_all('a', href=True):
            href = a['href']
            link_text = a.get_text(" ", strip=True).lower()
            if href.lower().endswith('.pdf'):
                pdf_url = urljoin(url, href)
                pdf_links.append({
                    "College Name": college,
                    "Found On": url,
                    "PDF Link": pdf_url
                })
                continue
            if ("faculty" in href or "staff" in href or "people" in href or
                "faculty" in link_text or "staff" in link_text or "people" in link_text or "department" in link_text):
                suburl = urljoin(url, href)
                if suburl != url and suburl not in visited:
                    print(f"Following sub-directory: {suburl}")
                    substaff += crawl(suburl, depth+1, root_url, visited, college)
        return staff + substaff
    except Exception as e:
        print(f"Failed at {url}: {e}")
        return []

df = pd.read_csv(input_csv)

if 'Status' not in df.columns:
    df['Status'] = False

if os.path.exists(output_csv):
    try:
        results_df = pd.read_csv(output_csv)
        results = results_df.to_dict('records')
    except pd.errors.EmptyDataError:
        results = []
else:
    results = []

for idx, row in df[df['Exists'] == True].iterrows():
    if row.get('Status', False):
        print(f"Skipping already scraped: {row['name'] if 'name' in row else row['College Name']}")
        continue

    url = row['Cleaned Link'] if 'Cleaned Link' in row else row['Faculty Directory Link']
    college = row['name'] if 'name' in row else row['College Name']
    print(f"\nCrawling {college}: {url}")
    
    visited = set()
    faculty_rows = crawl(url, 0, url, visited, college)
    print(f"Found {len(faculty_rows)} faculty entries for {college}")

    if faculty_rows:
        for entry in faculty_rows:
            results.append({
                "College Name": college,
                "Faculty Directory Link": url,
                "Name": entry['Name'],
                "Department": entry['Department'],
                "Email": entry['Email']
            })

    pd.DataFrame(results).drop_duplicates().to_csv(output_csv, index=False)
    if pdf_links:
        pd.DataFrame(pdf_links).drop_duplicates().to_csv(pdf_output_csv, index=False)
    
    df.at[idx, 'Status'] = True
    df.to_csv(input_csv, index=False)

    commit_progress(college)

driver.quit()
print(f"\nDone. All colleges processed.")
