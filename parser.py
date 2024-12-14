from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from decouple import config
import time

class LinkedInJobParser:
    def __init__(self):
        self.job_query = config('JOB_QUERY')
        self.driver = self._setup_driver()
        
    def _setup_driver(self):
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')  # Работа в фоновом режиме
        options.add_argument('--disable-gpu')
        service = Service(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=options)

    def login(self):
        self.driver.get('https://www.linkedin.com/login')
        
        email_input = self.driver.find_element(By.ID, 'username')
        password_input = self.driver.find_element(By.ID, 'password')
        
        email_input.send_keys(config('LINKEDIN_EMAIL'))
        password_input.send_keys(config('LINKEDIN_PASSWORD'))
        
        password_input.submit()
        time.sleep(3)  # Ждем загрузки после логина

    def get_jobs(self):
        search_url = f"https://www.linkedin.com/jobs/search/?keywords={self.job_query.replace(' ', '%20')}"
        self.driver.get(search_url)
        
        jobs = []
        
        # Ждем загрузки результатов
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "jobs-search__results-list"))
        )
        
        # Получаем список вакансий
        job_cards = self.driver.find_elements(By.CLASS_NAME, "jobs-search-results__list-item")
        
        for card in job_cards[:10]:  # Берем первые 10 вакансий
            try:
                title = card.find_element(By.CLASS_NAME, "job-card-list__title").text
                company = card.find_element(By.CLASS_NAME, "job-card-container__company-name").text
                location = card.find_element(By.CLASS_NAME, "job-card-container__metadata-item").text
                link = card.find_element(By.CLASS_NAME, "job-card-list__title").get_attribute('href')
                
                jobs.append({
                    'title': title,
                    'company': company,
                    'location': location,
                    'link': link
                })
            except Exception as e:
                print(f"Error parsing job card: {e}")
                
        return jobs

    def close(self):
        self.driver.quit()

def main():
    parser = LinkedInJobParser()
    try:
        parser.login()
        jobs = parser.get_jobs()
        
        # Вывод результатов
        for job in jobs:
            print("\n-------------------")
            print(f"Должность: {job['title']}")
            print(f"Компания: {job['company']}")
            print(f"Локация: {job['location']}")
            print(f"Ссылка: {job['link']}")
            
    finally:
        parser.close()

if __name__ == "__main__":
    main()
