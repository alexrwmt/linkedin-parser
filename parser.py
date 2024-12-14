import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from decouple import config
import time

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'linkedin_parser_{datetime.now().strftime("%Y%m%d")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class LinkedInJobParser:
    def __init__(self):
        self.job_query = config('JOB_QUERY')
        logger.info(f"Инициализация парсера для запроса: {self.job_query}")
        self.driver = self._setup_driver()
        
    def _setup_driver(self):
        logger.info("Настройка веб-драйвера...")
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        service = Service(ChromeDriverManager().install())
        logger.info("Веб-драйвер успешно настроен")
        return webdriver.Chrome(service=service, options=options)

    def login(self):
        logger.info("Попытка входа в LinkedIn...")
        try:
            self.driver.get('https://www.linkedin.com/login')
            
            email_input = self.driver.find_element(By.ID, 'username')
            password_input = self.driver.find_element(By.ID, 'password')
            
            email_input.send_keys(config('LINKEDIN_EMAIL'))
            password_input.send_keys(config('LINKEDIN_PASSWORD'))
            
            password_input.submit()
            time.sleep(3)
            logger.info("Успешный вход в систему")
        except Exception as e:
            logger.error(f"Ошибка при входе: {str(e)}")
            raise

    def get_jobs(self):
        logger.info(f"Начало поиска вакансий для запроса: {self.job_query}")
        search_url = f"https://www.linkedin.com/jobs/search/?keywords={self.job_query.replace(' ', '%20')}"
        self.driver.get(search_url)
        logger.info(f"Открыта страница поиска: {search_url}")
        
        jobs = []
        
        try:
            # Ждем загрузки результатов
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "jobs-search__results-list"))
            )
            logger.info("Страница с результатами успешно загружена")
            
            # Получаем список вакансий
            job_cards = self.driver.find_elements(By.CLASS_NAME, "jobs-search-results__list-item")
            logger.info(f"Найдено карточек с вакансиями: {len(job_cards)}")
            
            for index, card in enumerate(job_cards[:10], 1):
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
                    logger.info(f"Обработана вакансия {index}: {title} в компании {company}")
                except Exception as e:
                    logger.error(f"Ошибка при парсинге карточки {index}: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Ошибка при получении списка вакансий: {str(e)}")
            
        logger.info(f"Всего успешно обработано вакансий: {len(jobs)}")
        return jobs

    def close(self):
        logger.info("Закрытие браузера")
        self.driver.quit()

def main():
    logger.info("Запуск парсера")
    parser = LinkedInJobParser()
    try:
        parser.login()
        jobs = parser.get_jobs()
        
        # Вывод результатов
        for index, job in enumerate(jobs, 1):
            logger.info(f"\n--- Вакансия {index} ---")
            logger.info(f"Должность: {job['title']}")
            logger.info(f"Компания: {job['company']}")
            logger.info(f"Локация: {job['location']}")
            logger.info(f"Ссылка: {job['link']}")
            
    except Exception as e:
        logger.error(f"Критическая ошибка в работе парсера: {str(e)}")
    finally:
        parser.close()
        logger.info("Работа парсера завершена")

if __name__ == "__main__":
    main()
