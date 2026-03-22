with open('out_utf8.txt', 'w', encoding='utf-8') as f:
    f.write(open('out.txt', encoding='utf-16le').read())
