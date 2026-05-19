import pyautogui as pg
import time as tm

def chamada():
    try:
        pg.press('win')
        pg.write('firefox')
        pg.press('enter')
        tm.sleep(2)

    except Exception as e:
        print(f"Erro ao abir o navegador: {e}")

if __name__ == "__main__":
    chamada()
