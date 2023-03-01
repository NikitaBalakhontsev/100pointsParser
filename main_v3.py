import asyncio
import csv
import datetime
import re
from configparser import ConfigParser
from time import sleep

import aiohttp
from bs4 import BeautifulSoup

# pip install datetime aiohttp asyncio beautifulsoup4 configparser csv re lxml


CONFIG_NAME = "config.ini"



HOMEWORKS_DATA = []
FNAME = ""
LIMIT = 4 #limit of simultaneous processes


async def get_page_data(session, homework, page):
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
            print("No homework found")

        for user in users:
            href = user.find('a', class_="btn btn-xs bg-purple", href=True)['href']
            level = user.find_all('div')[7].find('b').text
            user_name = user.find_all('div')[2].text
            user_email = user.find_all('div')[3].text

            async with session.get(href + "?status=checking", headers=headers) as user_page_response:
                user_page_response_text = await user_page_response.text()
                user_page_soup = BeautifulSoup(user_page_response_text, 'lxml')
                try:
                    score_block = user_page_soup.find('div', class_="card-body").find('div',class_="row").find_all('div', class_="form-group col-md-3")[5].find_all('div')
                    #test_score = int(re.search("\d+", str(score_block[0].get_text()))[0])
                    curators_score = int(re.search("\d+", str(score_block[1].get_text()))[0])
                    score = curators_score
                except:
                    simple_score_block = user_page_soup.find('div', class_="card-body").find('div',class_="row").find_all('div', class_="form-group col-md-3")[5].find('div').text
                    match = re.search("\d+", str(simple_score_block))
                    score = match[0] if match else 'Not found'

            HOMEWORKS_DATA.append(
                {
                    "user_email": user_email,
                    "user_name": user_name,
                    "level": level,
                    "score": score,
                    "href": href + "?status=checked",
                }
             )

        print(f"[INFO] Обработал страницу #{page}")
            #await asyncio.sleep(0.2) add sleep to the process


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
    except:
        print("The configuration file could not be opened")
        exit(1)


    async with aiohttp.ClientSession() as session:
        response = await session.post(link, data=login_data, headers=headers)
        soup = BeautifulSoup(await response.text(), "lxml")

        try:
            if soup.find("form",{"action": "https://api.100points.ru/login", "method": "POST"}):
                raise Exception("Authorization error")
        except Exception:
            print("\nAuthorization error")
            exit(1)



        module_selection = None
        for x in range(0, 5):
            try:
                page = f"https://api.100points.ru/student_homework/index?status=passed&email=&name=&course_id={course_id}"
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
            raise ConnectionError("Module_selection error")

        module_selection = [str(module)[14:-9:].split("\"") for module in module_selection][1:]
        module_sorted = []
        for module in module_selection:
            module_sorted.append([int(module[1]), module[2][1:]])
        module_sorted.sort()
        for module in module_sorted:
            print(f"{module[0]} -- {module[1][:].lstrip()}")
        module_id = input("\nВведите id модуля (первое число): ")
        print()



        lesson_select = None
        for x in range(0, 5):
            try:
                page = f"https://api.100points.ru/student_homework/index?status=passed&email=&name=&course_id={course_id}&module_id={module_id}"
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
            raise ConnectionError("Lesson_selection error")


        lesson_select = [str(lesson)[14:-9:].split("\"") for lesson in lesson_select][1:]
        lesson_sorted = []
        for lesson in lesson_select:
            lesson_sorted.append([int(lesson[1]), lesson[2][1:]])
        lesson_sorted.sort()
        for lesson in lesson_sorted:
            print(f"{lesson[0]} -- {lesson[1].lstrip()}")
        lesson_id = input("\nВведите id урока (первое число): ")


        global FNAME
        FNAME = f"{module_id}-{lesson_id}"

        homework = page + f"&lesson_id={lesson_id}"
        homework_response = await session.get(homework, headers=headers)
        homework_soup = BeautifulSoup(await homework_response.text(), 'lxml')
        # end of choose lesson

        try:
            expected_block = homework_soup.find('div', id="example2_info").text
            expected = int(re.search(r'\d*$', expected_block.strip()).group())
            pages = expected // 15
            print("\nНайдено ", expected, " записи")
        except:
            pages = 0
            print("\nНайдено меньше 15 записей")


        limit = asyncio.Semaphore(LIMIT)
        tasks = []

        for page in range(1, 2 + pages):
            task = asyncio.create_task(get_page_data(session, homework, page))
            tasks.append(task)

        await asyncio.gather(*tasks)


def data_processing():
    data = []

    homeworks_data_sort = sorted(HOMEWORKS_DATA, key=lambda d: d['user_email'])

    print(*homeworks_data_sort, sep = '\n')

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
                }
            )

        if homework["level"] == "Базовый уровень":
            if int(homework["score"]) > int(data[-1]["score_easy"]):
                data[-1]["score_easy"] = homework["score"]
                data[-1]["href_easy"] = homework["href"]

        elif homework["level"] == "Средний уровень":
            if int(homework["score"]) > int(data[-1]["score_middle"]):
                data[-1]["score_middle"] = homework["score"]
                data[-1]["href_middle"] = homework["href"]

        elif homework["level"] == "Сложный уровень":
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
                "Ссылка на сложный уровень"
            )
        )
    try:
        config = ConfigParser()
        config.read(CONFIG_NAME)

        if(config.getboolean('email','filling_in_the_template') == True):
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
                        user["href_hard"]
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
                        user["href_hard"]
                    )
                )
    print("Saved file  " + f"{FNAME}--{cur_time}.csv")


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
    main()
