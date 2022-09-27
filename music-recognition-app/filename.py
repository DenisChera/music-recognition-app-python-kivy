song = 'SAINt JHN - Roses(Imanbek Remix).wav'
x = song.split(' - ')
#print("ARTIST " + x[0])
print(x)

if(len(x) == 3):
    y = x[2].split('.wav')
    sn = x[1] + ' - ' + y[0]
else:
    y = x[1].split('.wav')
    sn = y[0]

print(sn)
