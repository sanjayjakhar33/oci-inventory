from openpyxl import Workbook


def create_workbook():

    wb = Workbook()

    default = wb.active
    wb.remove(default)

    return wb
