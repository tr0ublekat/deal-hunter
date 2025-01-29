import asyncio

from aiogram import types
from aiogram import F
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandObject
from sqlalchemy import delete
from sqlalchemy.future import select


from config import *
from main import dp, bot
from database import async_session
from models import User, Product

import time
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from undetected_geckodriver import Firefox
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

options = Options()
options.add_argument("--headless")
driver = Firefox(options=options)

@dp.message(F.text.lower() == "да")
async def delete_user(message: types.Message):
    try:
        async with async_session() as session:
            user = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
            user = user.scalar()

            if not user:
                await message.reply("Пользователь не найден в базе данных.", reply_markup=types.ReplyKeyboardRemove())
                return

            await session.execute(
                delete(Product).where(Product.user_id == user.id)
            )

            await session.execute(
                delete(User).where(User.id == user.id)
            )

            await session.commit()

        await message.answer(f"Нажмите на /start, чтобы начать!", reply_markup=types.ReplyKeyboardRemove())

    except Exception as e:
        print(e)
        await message.answer("Произошла ошибка при пересоздании учетной записи!", reply_markup=types.ReplyKeyboardRemove())

@dp.message(F.text.lower() == "нет")
async def dont_delete_user(message: types.Message):
    await message.reply("Отлично, продолжаем!", reply_markup=types.ReplyKeyboardRemove())

@dp.message(Command("start"))
async def create_user(message: types.Message):
    async with async_session() as session:
        new_user = User(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            full_name=message.from_user.full_name,
        )
        session.add(new_user)
        try:
            await session.commit()
            await message.answer(
                "Привет! 👋\n"
                "Я бот для мониторинга цен на товары. 🛒\n"
                "Отправьте ссылку на товар, и я начну отслеживать его цену. 📉\n\n"
                "Доступные сайты на данный момент: DNS\n\n"
                "Команды, которые вы можете использовать:\n"
                "/help - получить список доступных команд\n"
                "/add <url>- добавить товар для мониторинга\n"
                "/remove <url> - удалить товар из мониторинга\n"
                "/list - посмотреть список отслеживаемых товаров\n"
            )

        except Exception as e:
            await session.rollback()
            kb = [
                [
                    types.KeyboardButton(text="Да"),
                    types.KeyboardButton(text="Нет")
                ]
            ]
            keyboard = types.ReplyKeyboardMarkup(
                keyboard=kb,
                resize_keyboard=True,
                input_field_placeholder="Удалить все отслеживаемые товары?"
            )
            await message.answer("У вас уже есть отслеживаемые товары!\nВы хотите удалить все товары?", reply_markup=keyboard)

@dp.message(Command("help"))
async def nothing(message: types.Message):
    await message.answer(
        "Привет! 👋\n"
        "Я бот для мониторинга цен на товары. 🛒\n"
        "Отправьте ссылку на товар, и я начну отслеживать его цену. 📉\n\n"
        "Доступные сайты на данный момент: DNS\n\n"
        "Команды, которые вы можете использовать:\n"
        "/help - получить список доступных команд\n"
        "/add <url>- добавить товар для мониторинга\n"
        "/remove <url> - удалить товар из мониторинга\n"
        "/list - посмотреть список отслеживаемых товаров\n"
    )

async def check_product(url: str):
    try:
        driver.get(url)

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, 'product-card-top__title'))
        )
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, 'product-buy__price'))
        )

        if "dns-shop.ru" in url:
            title = driver.find_element(By.CLASS_NAME, 'product-card-top__title').text
            value = driver.find_element(By.CLASS_NAME, 'product-buy__price')

            try:
                old_value = value.find_element(By.CLASS_NAME, 'product-buy__prev')
                temp = value.text
                value = ''
                for t in temp:
                    value += t
                    if (t == ' ') or (t.isdigit()):
                        pass
                    else:
                        break

            except Exception as e:
                value = value.text

            parts = value.split()
            price = "".join(parts[:-1])  # Все части, кроме последней, объединяем в одну строку
            curr = parts[-1]  # Последний элемент - валюта

            print(f"Название: {title}\n"
                  f"Цена: {price}\n"
                  f"Валюта: {curr}")

            return title, price, curr
        elif "ozon.ru" in url:
            ...
        else:
            return None
    except Exception as e:
        print(f"Ошибка при парсинге! {e}")
        return None


@dp.message(Command("add"))
async def add_product(message: types.Message, command: CommandObject):
    try:
        args = command.args.split(" ")
        url = args[0]
        await message.reply("Подождите, идет обработка...")

        result = await check_product(url)
        if result is None:
            await message.reply("Произошла ошибка. Попробуйте еще раз!")

        else:
            title = str(result[0])
            price = float(result[1])
            curr = str(result[2])

            async with async_session() as session:
                current_user_result = await session.execute(
                    select(User).where(User.telegram_id == message.from_user.id)
                )
                current_user = current_user_result.scalar()

                if not current_user:
                    await message.reply("Пользователь не найден в базе данных. Зарегистрируйтесь через /start.")
                    return

                existing_product = await session.execute(
                    select(Product).where(Product.url == url, Product.user_id == current_user.id)
                )
                existing_product = existing_product.scalar()

                if existing_product:
                    await message.reply("Этот товар уже добавлен для отслеживания.")
                    return

                session.add(Product(
                    name=title,
                    price=price,
                    currency=curr,
                    url=url,
                    user_id=current_user.id,
                ))
                await session.commit()
            await message.reply("Товар успешно добавлен для отслеживания!")

    except Exception as e:
        await message.reply(f"Проверьте правильность добавления товара!\nШаблон: /add <url>")
        print(f"Ошибка: {e}")
        return

    async with async_session() as session:
        pass

@dp.message(Command("remove"))
async def remove_product(message: types.Message, command: CommandObject):
    try:
        # Проверяем, передан ли URL
        if not command.args:
            await message.reply("Укажите ссылку на товар, который нужно удалить. Пример: /remove <url>")
            return

        url = command.args.strip()  # Получаем URL

        async with async_session() as session:
            # Ищем пользователя
            current_user_result = await session.execute(
                select(User).where(User.telegram_id == message.from_user.id)
            )
            current_user = current_user_result.scalar()

            if not current_user:
                await message.reply("Пользователь не найден в базе данных. Зарегистрируйтесь через /start.")
                return

            # Ищем товар по URL и пользователю
            product_result = await session.execute(
                select(Product).where(Product.url == url, Product.user_id == current_user.id)
            )
            product = product_result.scalar()

            if not product:
                await message.reply("Товар с указанной ссылкой не найден среди ваших отслеживаемых.")
                return

            # Удаляем товар
            await session.delete(product)
            await session.commit()

            await message.reply(f"Товар '{product.name}' успешно удален из отслеживаемых!")

    except Exception as e:
        await message.reply("Произошла ошибка при удалении товара. Попробуйте позже.")
        print(f"Ошибка: {e}")

@dp.message(Command("list"))
async def get_products(message: types.Message):
    try:
        async with async_session() as session:
            current_user_result = await session.execute(
                select(User).where(User.telegram_id == message.from_user.id)
            )
            current_user = current_user_result.scalar()

            if not current_user:
                await message.reply("Пользователь не найден в базе данных. Зарегистрируйтесь через /start.")
                return

            products_result = await session.execute(
                select(Product).where(Product.user_id == current_user.id)
            )
            products = products_result.scalars().all()

            if not products:
                await message.reply("У вас нет отслеживаемых товаров.")
                return

            # Отправляем информацию о каждом товаре
            for product in products:
                await message.answer(
                    f"Название: {product.name}\n"
                    f"Стоимость: {product.price} {product.currency}\n"
                    f"Ссылка: {product.url}"
                )

    except Exception as e:
        await message.answer("Произошла ошибка при получении всех товаров!")
        print(e)

@dp.message()
async def nothing(message: types.Message):
    await message.answer("Что-то пошло не так!")



async def fetch_product_price(url: str):
    try:
        driver.get(url)

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, 'product-card-top__title'))
        )
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, 'product-buy__price'))
        )

        if "dns-shop.ru" in url:
            value = driver.find_element(By.CLASS_NAME, 'product-buy__price').text
            parts = value.split()
            price = "".join(parts[:-1])  # Все части, кроме последней, объединяем в одну строку
            curr = parts[-1]  # Последний элемент - валюта
            return price, curr
        elif "ozon.ru" in url:
            ...
        else:
            return None, None
    except Exception as e:
        print(f"Ошибка при получении цены: {e}")
        return None, None

async def check_prices_periodically():
    print("Попытка получить обновленные цены!")
    while True:
        try:
            async with async_session() as session:
                products_result = await session.execute(select(Product))
                products = products_result.scalars().all()

                for product in products:
                    new_price, new_currency = await fetch_product_price(product.url)

                    if new_price is None:
                        print(f"Ошибка при проверке цены для товара {product.name}")
                        continue

                    # Если цена изменилась, уведомляем пользователя
                    if float(new_price) != product.price:
                        print(f"Цена на продукт {product.name} изменилась!")
                        user_result = await session.execute(select(User).where(User.id == product.user_id))
                        user = user_result.scalar()

                        if user:
                            await bot.send_message(
                                chat_id=user.telegram_id,
                                text=(
                                    f"Цена изменилась для товара: *{product.name}*\n"
                                    f"Было: {product.price} {product.currency}\n"
                                    f"Стало: {new_price} {new_currency}\n\n"
                                    f"[Посмотреть товар]({product.url})"
                                ),
                                parse_mode=ParseMode.HTML
                            )

                        # Обновляем цену в базе данных
                        product.price = float(new_price)
                        product.currency = new_currency
                        session.add(product)

                await session.commit()

        except Exception as e:
            print(f"Ошибка в периодической задаче: {e}")

        # Ждём 30 минут
        await asyncio.sleep(TIMEOUT_FOR_UPDATING)