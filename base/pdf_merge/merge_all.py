from pathlib import Path
from PyPDF2 import PdfMerger

def merge_all_pdf(pdf_dir):
    # 定义 PDF 文件所在的目录路径，使用当前工作目录下的 'practice_files' 文件夹 
    print ("merge all pdf in dir "+pdf_dir)
    #pdf_dirs = Path.cwd() / 'merge'.
    pdf_dirs = Path.cwd() / pdf_dir

    # 使用 glob 方法查找以 '.pdf' 结尾的所有 PDF 文件
    pdf_files = list(pdf_dirs.glob('*.pdf'))  

    # 将文件列表按数字顺序排列
    pdf_files.sort() 

    # 创建一个 PdfMerger 对象，用于合并 PDF 文件
    pdf_merger = PdfMerger()

    # 遍历排序后的 PDF 文件列表，最多合并前两个文件
    for pdf_file in pdf_files:  # 只处理前两个文件
        pdf_merger.append(pdf_file)  # 将每个 PDF 文件添加到合并器中

    # 在用户主目录下创建一个新的 PDF 文件 'concatenated.pdf'，以写入模式打开
    with Path.cwd().joinpath('merge.pdf').open('wb') as f:
        pdf_merger.write(f)  # 将合并后的内容写入新文件

if __name__ == "__main__":
    merge_all_pdf('merge')