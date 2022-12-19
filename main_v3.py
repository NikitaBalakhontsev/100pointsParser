import re
import csv
from configparser import ConfigParser
from bs4 import BeautifulSoup
import asyncio
import aiohttp
import datetime
# pip install datetime aiohttp asyncio bs4 configparser csv re lxml



homeworks_data = []
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
            lavel = user.find_all('div')[7].find('b').text
            user_name = user.find_all('div')[2].text
            user_email = user.find_all('div')[3].text

            async with session.get(href + "?status=checking", headers=headers) as user_page_response:
                user_page_response_text = await user_page_response.text()
                user_page_soup = BeautifulSoup(user_page_response_text, 'lxml')

                try:
                    score = 0
                    score_block = user_page_soup.find('div', class_="card-body").find('div',class_="row").find_all('div', class_="form-group col-md-3")[5].find_all('div')
                    score_block[0] = re.search("\d+", str(score_block[0].get_text()))[0]
                    score_block[1] = re.search("\d+", str(score_block[1].get_text()))[0]
                    if score_block[0] != score_block[1]:
                        score = score_block[0] + score_block[1]
                    else:
                        score = score_block[0]
                except:
                    score_block = user_page_soup.find('div', class_="card-body").find('div',class_="row").find_all('div', class_="form-group col-md-3")[5].find('div').text
                    match = re.search("\d+", str(score_block))
                    score = match[0] if match else 'Not found'

            homeworks_data.append(
                {
                    "user_email": user_email,
                    "user_name": user_name,
                    "lavel": lavel,
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

    config = ConfigParser()
    config.read('config.ini')
    login_data = {
        'email':  config['main']['email'],
        'password': config['main']['password'],
    }

    course_id = config['main']['course_id']

    async with aiohttp.ClientSession() as session:
        response = await session.post(link, data=login_data, headers=headers)
        soup = BeautifulSoup(await response.text(), "lxml")

        try:
            if soup.find("form",{"action": "https://api.100points.ru/login", "method": "POST"}):
                raise Exception("Authorization error")
        except Exception:
            print("\nAuthorization error")
            exit(1)

        page = f"https://api.100points.ru/student_homework/index?status=passed&email=&name=&course_id={course_id}"
        page_response = await session.get(page, headers=headers)
        page_soup = BeautifulSoup(await page_response.text(), "lxml")

        module_select = page_soup.find("div", {"class": "form-group", "id": "module_select"}).find_all('option')
        module_select = [str(module)[14:-9:].split("\"") for module in module_select][1:]
        module_sorted = []
        for module in module_select:
            module_sorted.append([int(module[1]), module[2][1:]])
        module_sorted.sort()
        for module in module_sorted:
            print(f"{module[0]} -- {module[1][:].lstrip()}")
        module_id = input("\nВведите id модуля (первое число): ")
        print()

        page = f"https://api.100points.ru/student_homework/index?status=passed&email=&name=&course_id={course_id}&module_id={module_id}"
        page_response = await session.get(page, headers=headers)
        page_soup = BeautifulSoup(await page_response.text(), 'lxml')

        lesson_select = page_soup.find("div", {"class": "form-group", "id": "lesson_select"}).find_all('option')
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
            pages = len(
                homework_soup.find('div', id="example2_paginate").find_all("li", class_="paginate_button page-item"))
            expected = homework_soup.find('div', id="example2_info").text
            print("\nFound ", expected[47:49], " tokens")
        except:
            pages = 0
            print("\nLess than 15 tokens expected")


        limit = asyncio.Semaphore(LIMIT)
        tasks = []

        for page in range(1, 2 + pages):
            task = asyncio.create_task(get_page_data(session, homework, page))
            tasks.append(task)

        await asyncio.gather(*tasks)


def data_processing():
    data = []

    homeworks_data_sort = sorted(homeworks_data, key=lambda d: d['user_email'])

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

        if homework["lavel"] == "Базовый уровень":
            if int(homework["score"]) > int(data[-1]["score_easy"]):
                data[-1]["score_easy"] = homework["score"]
                data[-1]["href_easy"] = homework["href"]

        elif homework["lavel"] == "Средний уровень":
            if int(homework["score"]) > int(data[-1]["score_middle"]):
                data[-1]["score_middle"] = homework["score"]
                data[-1]["href_middle"] = homework["href"]

        elif homework["lavel"] == "Сложный уровень":
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

    for user in data:
        with open(f"{FNAME}--{cur_time}.csv", "a", newline="") as file:
            writer = csv.writer(file, delimiter=";")
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
