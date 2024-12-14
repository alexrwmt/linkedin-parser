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
import pickle
import os
from pathlib import Path
from twocaptcha import TwoCaptcha
import re
from selenium.webdriver.common.action_chains import ActionChains

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

def timeit(method):
    """Декоратор для измерения времени выполнения функций"""
    def timed(*args, **kwargs):
        start_time = time.time()
        result = method(*args, **kwargs)
        end_time = time.time()
        duration = end_time - start_time
        logger.info(f'Функция {method.__name__} выполнилась за {duration:.2f} секунд')
        return result
    return timed

class LinkedInJobParser:
    def __init__(self):
        self.job_query = config('JOB_QUERY')
        self.start_time = time.time()
        
        # Создаем папку для текущего запуска
        self.run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_folder = Path(f'parser_runs/{self.run_timestamp}')
        self.run_folder.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Инициализация парсера для запроса: {self.job_query}")
        logger.info(f"Создана папка для текущего запуска: {self.run_folder}")
        
        self.driver = self._setup_driver()

    def _setup_driver(self):
        logger.info("Настройка веб-драйвера...")
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--disable-blink-features=AutomationControlled')  # Скрываем автоматизацию
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument('user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        # Скрываем признаки автоматизации
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        driver.implicitly_wait(10)
        logger.info("Веб-драйвер успешно настроен")
        return driver

    def set_cookies(self):
        """Установка сохраненных куки"""
        logger.info("Установка сохраненных cookies...")
        try:
            # Сначала открываем LinkedIn для установки домена
            self.driver.get('https://www.linkedin.com')
            time.sleep(2)
            
            # Добавляем основные куки
            cookies = {
                'li_at': config('LINKEDIN_COOKIE_LI_AT'),
                'JSESSIONID': config('LINKEDIN_COOKIE_JSESSIONID')
            }
            
            for name, value in cookies.items():
                cookie = {
                    'name': name,
                    'value': value,
                    'domain': '.linkedin.com'
                }
                self.driver.add_cookie(cookie)
                logger.info(f"Добавлен cookie: {name}")
            
            # Обновляем страницу
            self.driver.refresh()
            time.sleep(3)
            self.save_screenshot('after_cookies_set')
            
            if self._is_logged_in():
                logger.info("Успешная авторизация через cookies")
                return True
            else:
                logger.error("Не удалось войти через cookies")
                return False
                
        except Exception as e:
            logger.error(f"Ошибка при установке cookies: {str(e)}")
            return False

    def login(self):
        """Авторизация через установку cookies"""
        logger.info("Попытка входа в LinkedIn...")
        
        if self.set_cookies():
            return True
            
        logger.error("Не удалось войти через cookies")
        raise Exception("Login failed")

    def _is_logged_in(self):
        """Проверка статуса авторизации"""
        try:
            # Проверяем несколько элементов, которые видны только после входа
            selectors = [
                '.global-nav__me-photo',
                '.global-nav__primary-link',
                'div[data-control-name="identity_profile_photo"]'
            ]
            
            for selector in selectors:
                try:
                    self.driver.find_element(By.CSS_SELECTOR, selector)
                    logger.info(f"Найден элемент авторизации: {selector}")
                    return True
                except:
                    continue
                    
            return False
        except Exception as e:
            logger.error(f"Ошибка при проверке авторизации: {str(e)}")
            return False

    def save_screenshot(self, name):
        """Сохранение скриншота с временной меткой"""
        timestamp = datetime.now().strftime("%H%M%S")
        filename = f"{timestamp}_{name}.png"
        filepath = self.run_folder / filename
        try:
            self.driver.save_screenshot(str(filepath))
            logger.info(f"Сохранен скриншот: {filename}")
        except Exception as e:
            logger.error(f"Ошибка при сохранении скриншота {filename}: {str(e)}")

    def solve_captcha(self):
        """Решение капчи с помощью 2captcha"""
        logger.info("Обнаружена капча, пытаемся решить...")
        try:
            self.save_screenshot('before_verify_click')
            
            # Пробуем разные способы найти кнопку Verify
            verify_button_selectors = [
                'button[id="home_children_button"]',
                'button.sc-bdnxRM.DRUpX',
                'button[aria-describedby="descriptionVerify"]',
                'button:contains("Verify")'
            ]
            
            verify_button = None
            for selector in verify_button_selectors:
                try:
                    logger.info(f"Пробуем найти кнопку по селектору: {selector}")
                    verify_button = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    if verify_button:
                        logger.info(f"Кнопка найдена по селектору: {selector}")
                        break
                except Exception as e:
                    logger.warning(f"Селектор {selector} не сработал: {str(e)}")
                    continue
            
            if not verify_button:
                # Если не нашли по селекторам, пробуем JavaScript
                logger.info("Пробуем нажать кнопку через JavaScript")
                self.driver.execute_script("""
                    document.querySelector('button[aria-describedby="descriptionVerify"]').click();
                """)
                self.save_screenshot('after_js_click')
            else:
                # Если нашли кнопку, пробуем разные способы клика
                try:
                    logger.info("Пробуем обычный клик")
                    verify_button.click()
                except:
                    try:
                        logger.info("Пробуем клик через Actions")
                        actions = ActionChains(self.driver)
                        actions.move_to_element(verify_button)
                        actions.click()
                        actions.perform()
                    except:
                        logger.info("Пробуем клик через JavaScript")
                        self.driver.execute_script("arguments[0].click();", verify_button)
            
            self.save_screenshot('after_verify_click')
            logger.info("Попытка нажатия кнопки Verify выполнена")
            
            # Ждем изменений на странице
            time.sleep(5)
            self.save_screenshot('after_verify_wait')
            
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при нажатии кнопки Verify: {str(e)}")
            self.save_screenshot('verify_error')
            return False

    def _log_timing(self, action):
        """Вспомогательный метод для логирования времени"""
        current_time = time.time()
        elapsed = current_time - self.start_time
        logger.info(f"[TIMING] {action}: {elapsed:.2f} секунд с начала работы")
    
    @timeit
    def get_jobs(self):
        logger.info(f"Начало поиска вакансий для запроса: {self.job_query}")
        search_url = f"https://www.linkedin.com/jobs/search/?keywords={self.job_query.replace(' ', '%20')}"
        
        try:
            self.driver.get(search_url)
            self.save_screenshot('search_page_initial')
            
            time.sleep(5)
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            self.save_screenshot('after_scroll')
            
            time.sleep(2)
            
            # ... остальной код метода get_jobs ...
            # Добавляйте self.save_screenshot() в ключевых местах
            
        except Exception as e:
            logger.error(f"Ошибка при получении списка вакансий: {str(e)}")
            self.save_screenshot('jobs_error')
            raise

    def close(self):
        logger.info("Закрытие браузера")
        self.driver.quit()

def main():
    logger.info("Запуск парсера")
    parser = LinkedInJobParser()
    try:
        parser.login()
        jobs = parser.get_jobs()
    except Exception as e:
        logger.error(f"Критическая ошибка в работе парсера: {str(e)}")
    finally:
        parser.close()
        logger.info("Работа парсера завершена")

if __name__ == "__main__":
    main()
