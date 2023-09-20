import asyncio
import csv
import datetime
import re
from configparser import ConfigParser
import time
import aiohttp
from bs4 import BeautifulSoup
from prettytable import PrettyTable


# pip install datetime aiohttp asyncio beautifulsoup4 configparser csv re lxml
 

LIMIT = 10 #limit the number of pages to be requestede at the same time
CONFIG_NAME = "scraper.ini"

HOMEWORKS_DATA = []
FNAME = ""



async def get_page_data(session, homework, page, semaphore):
    async with semaphore:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/104.0.5112.102 Safari/537.36 OPR/90.0.4480.84 (Edition Yx 08) '
        }

        page_link = homework + "&page=" + str(page)

        async with session.get(page_link, headers=headers) as table_response:

            table_response_text = await table_response.text()
            table_soup = BeautifulSoup(table_response_text, 'lxml')

            users = table_soup.find('table', id="example2").find_all('tr', class_="odd")
            if len(users) == 0:
                print("[INFO] No homework found")

            for user in users:

                try:
                    user_table = user.find_all('td')

                    href = user_table[0].find('a', class_="btn btn-xs bg-purple", href=True)['href']
                    user_name = user_table[2].find_all('div')[0].text
                    user_email = user_table[2].find_all('div')[1].text
                    level = user_table[3].find_all('div')[3].find('b').text.split()[0]
                   
                    
                    async with session.get(href + "?status=checking", headers=headers) as user_page_response:
                        user_page_response_text = await user_page_response.text()
                        user_page_soup = BeautifulSoup(user_page_response_text, 'lxml')
                        user_homework_table = user_page_soup.find('div', class_="card-body").find('div',class_="row").find_all('div', class_="form-group col-md-3")
                        try:
                            score_block = user_homework_table[5].find_all('div')
                            #test_score = int(re.search("\d+", str(score_block[0].get_text()))[0])
                            curators_score = int(re.search("\d+", str(score_block[1].get_text()))[0])
                            score = curators_score
                        except:
                            simple_score_block = user_homework_table[5].find('div').text
                            match = re.search("\d+", str(simple_score_block))
                            score = match[0] if match else 'Not found'

                        try:
                            curator_data = user_homework_table[3].find_all('div')[1].find_all('b')
                            duty_curator = curator_data[0].text
                            curator = curator_data[1].text
                        except:
                            duty_curator = "Not found"
                            curator = "Not found"

                    HOMEWORKS_DATA.append(
                        {
                            "user_email": user_email,
                            "user_name": user_name,
                            "level": level,
                            "score": score,
                            "href": href + "?status=checked",
                            "duty_curator": duty_curator,
                            "curator" : curator
                        }
                     )
                except:
                    print("\n[ERROR] No access to ",  href + "?status=checking", "\n")  

            print(f"[INFO] Обработал страницу #{page}")
            #await asyncio.sleep(0.1)


async def gather_data():
    link = "https://api.100points.ru/login"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/104.0.5112.102 Safari/537.36 OPR/90.0.4480.84 (Edition Yx 08) '
    }

    try:
        config = ConfigParser()
        config.read(CONFIG_NAME)
        login_data = {
            'email':  config['main']['email'],
            'password': config['main']['password'],
        }

        course_id = config['main']['course_id']
        group_id = config['main']['group_id']
    except:
        print("\n[ERROR] The configuration file could not be opened")
        input("Press Enter to close the window...")
        exit(1)


    async with aiohttp.ClientSession() as session:
        response = await session.post(link, data=login_data, headers=headers)
        soup = BeautifulSoup(await response.text(), "lxml")

        try:
            if soup.find("form",{"action": "https://api.100points.ru/login", "method": "POST"}):
                raise Exception("Authorization error")
        except Exception:
            print("\n[ERROR] Authorization error")
            input("Press Enter to close the window...")
            exit(1)



        module_selection = None
        for x in range(0, 5):
            try:
                page = f"https://api.100points.ru/student_homework/index?status=passed&email=&name=&course_id={course_id}&group_id={group_id}"
                page_response = await session.get(page, headers=headers)
                page_soup = BeautifulSoup(await page_response.text(), "lxml")
                module_selection = page_soup.find("select", {"class": "form-control", "id": "module_id"}).find_all('option')
                connection_error = None
            except Exception as connection_error:
                pass

            if connection_error:
                sleep(0.5)
            else:
                break
        if not module_selection:
            raise ConnectionError("\n[ERROR] Module_selection error")

        module_selection = [str(module)[14:-9:].split("\"") for module in module_selection][1:]
        module_id_list = []
        module_sorted = []
        for module in module_selection:
            module_sorted.append([int(module[1]), module[2][1:]])
            module_id_list.append(int(module[1]))
        module_sorted.sort()
        module_id_list.sort()

        print("---Выбор модуля--- \n")
        for module in module_sorted:
            print(f"{module[0]} -- {module[1][:].lstrip()}")

        module_id = int(input("\nВведите id модуля (число): "))

        while module_id not in module_id_list:
            print("\n\n")
            for module in module_sorted:
                print(f"{module[0]} -- {module[1][:].lstrip()}")
            print("Доступные id: " , *module_id_list)
            module_id = int(input("\nВведите доступный id : "))


        lesson_select = None
        for x in range(0, 5):
            try:
                page = f"https://api.100points.ru/student_homework/index?status=passed&email=&name=&course_id={course_id}&module_id={module_id}&group_id={group_id}"
                page_response = await session.get(page, headers=headers)
                page_soup = BeautifulSoup(await page_response.text(), 'lxml')
                lesson_select = page_soup.find("select", {"class": "form-control", "id": "lesson_id"}).find_all('option')
                connection_error = None
            except Exception as connection_error:
                pass

            if connection_error:
                sleep(0.5)
            else:
                break
        if not lesson_select :
            raise ConnectionError("\n[ERROR] Lesson_selection error")
            input("Press Enter to close the window...")


        lesson_select = [str(lesson)[14:-9:].split("\"") for lesson in lesson_select][1:]
        lesson_sorted = []
        lesson_id_list = []
        for lesson in lesson_select:
            lesson_sorted.append([int(lesson[1]), lesson[2][1:]])
            lesson_id_list.append(int(lesson[1]))
        lesson_sorted.sort()
        lesson_id_list.sort()

        print("\n---Выбор урока--- \n")
        for lesson in lesson_sorted:
            print(f"{lesson[0]} -- {lesson[1].lstrip()}")
        lesson_id = int(input("\nВведите id урока (число): "))
        
        while lesson_id not in lesson_id_list:
            print("\n\n")
            for lesson in lesson_sorted:
                print(f"{lesson[0]} -- {lesson[1].lstrip()}")
            print("Доступные id: " , *lesson_id_list)
            lesson_id = int(input("\nОшибка. Введите доступный id :"))

        global FNAME
        FNAME = f"{module_id}-{lesson_id}"

        try:
            homework = page + f"&lesson_id={lesson_id}"
            homework_response = await session.get(homework, headers=headers)
            homework_soup = BeautifulSoup(await homework_response.text(), 'lxml')
        except:
            print("\n[ERROR] Cannot open the selected lesson")
            input("Press Enter to close the window...")
            exit(1)
        # end of choose lesson

        try:
            expected_block = homework_soup.find('div', id="example2_info").text
            expected = int(re.search(r'\d*$', expected_block.strip()).group())
            pages = expected // 15
            print("\n[INFO] Найдено ", expected, " записи")
        except:
            pages = 0
            print("\n[INFO]Найдено меньше 15 записей")

        
        semaphore = asyncio.Semaphore(LIMIT)
        
        tasks = [asyncio.create_task(get_page_data(session, homework, page, semaphore)) for page in range(1, 2 + pages)]

        await asyncio.gather(*tasks)


def data_processing():
    data = []

    homeworks_data_sort = sorted(HOMEWORKS_DATA, key=lambda d: d['user_email'])
    
    try:
        config = ConfigParser()
        config.read(CONFIG_NAME)
        if(config.getboolean('setting','show_homeworks_in_the_terminal') == True):
            headers = ['user_email', 'user_name', 'level', 'score', "duty_curator", "curator"]
            table = PrettyTable(headers)
            for row in homeworks_data_sort:
                table.add_row([row[header.lower()] for header in headers])
            print(table)
    except Exception:
        print("[WARNING] The parameter value 'show_homeworks_in_the_terminal' from the configuration file is not defined")
        pass


    for homework in homeworks_data_sort:
        if not (data) or data[-1]["user_email"] != homework["user_email"]:
            data.append(
                {
                    "user_email": homework["user_email"],
                    "user_name": homework["user_name"],
                    "score_easy": '0',
                    "score_middle": '0',
                    "score_hard": '0',
                    "href_easy": '',
                    "href_middle": '',
                    "href_hard": '',
                    "duty_curator" : homework["duty_curator"],
                    "curator" : homework["curator"]
                }
            )

        if homework["level"] == "Базовый":
            if int(homework["score"]) > int(data[-1]["score_easy"]):
                data[-1]["score_easy"] = homework["score"]
                data[-1]["href_easy"] = homework["href"]

        elif homework["level"] == "Средний":
            if int(homework["score"]) > int(data[-1]["score_middle"]):
                data[-1]["score_middle"] = homework["score"]
                data[-1]["href_middle"] = homework["href"]

        elif homework["level"] == "Сложный":
            if int(homework["score"]) > int(data[-1]["score_hard"]):
                data[-1]["score_hard"] = homework["score"]
                data[-1]["href_hard"] = homework["href"]
    return data


def output_in_csv(data):
    cur_time = datetime.datetime.now().strftime("%d_%m_%Y_%H_%M")

    with open(f"{FNAME}--{cur_time}.csv", "w", newline="") as file:
        writer = csv.writer(file, delimiter=";")

        writer.writerow(
            (
                "Почта",
                "Имя Фамилия",
                "Базовый уровень",
                "Средний уровень",
                "Сложный уровень",
                "Ссылка на базовый уровень",
                "Ссылка на средний уровень",
                "Ссылка на сложный уровень",
                "Дежурный куратор",
                "Куратор"
            )
        )
    try:
        config = ConfigParser()
        config.read(CONFIG_NAME)

        if(config.getboolean('setting','filling_in_the_template') == True):
            count = int(config['email']['count'])

            users_pattern = []
            for i in range(1, count + 1):
                users_pattern.append(config['email'][f'item{i}'])

            current_data = []

            for user in users_pattern:
                for item in data:
                    if item["user_email"] == user:
                        current_data.append(item)
                        break
                else:
                    current_data.append( dict(
                        {
                            "user_email": user,
                            "user_name": '',
                            "score_easy": '0',
                            "score_middle": '0',
                            "score_hard": '0',
                            "href_easy": '',
                            "href_middle": '',
                            "href_hard": '',
                            "duty_curator" : '',
                            "curator" : ''
                        }))
            data = current_data
    except Exception:
        pass



    for user in data:
        with open(f"{FNAME}--{cur_time}.csv", "a", newline="") as file:
            writer = csv.writer(file, delimiter=";")
            try:
                writer.writerow(
                    (
                        user["user_email"],
                        user["user_name"],
                        user["score_easy"],
                        user["score_middle"],
                        user["score_hard"],
                        user["href_easy"],
                        user["href_middle"],
                        user["href_hard"],
                        user["duty_curator"],
                        user["curator"]
                    )
                )
            except:
                writer.writerow(
                    (
                        user["user_email"],
                        "Иероглифы",
                        user["score_easy"],
                        user["score_middle"],
                        user["score_hard"],
                        user["href_easy"],
                        user["href_middle"],
                        user["href_hard"],
                        user["duty_curator"],
                        user["curator"]
                    )
                )
    print("[INFO]Saved file  " + f"{FNAME}--{cur_time}.csv")


def main():    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(gather_data())
        
        data = data_processing()
        
        output_in_csv(data)
        
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    start = time.time()
    main()
    end = time.time()
    print("[INFO]The time of execution of above program is :",
      (end-start), "s")
    input("Press Enter to close the window...")
