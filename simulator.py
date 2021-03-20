import random
import csv

csv_columns = ['nodeamount', 'sn' ,'minimum', 'maximum', 'average']
csv_file = "simulation.csv"

try:
    with open(csv_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=csv_columns)
        writer.writeheader
        csvfile.close()
except IOError:
    print("I/O error")
n = [
1,
2,
3,
4,
5,
6,
7,
8,
9,
10,
11,
12,
13,
14,
15,
16,
17,
18,
19,
20,
21,
22,
23,
24,
25,
26,
27,
28,
29,
30,
31,
32,
33,
34,
35,
36,
37,
38,
39,
40,
41,
42,
43,
44,
45,
46,
47,
48,
49,
50,
51,
52,
53,
54,
55,
56,
57,
58,
59,
60,
61,
62,
63,
64,
65,
66,
67,
68,
69,
70,
71,
72,
73,
74,
75,
76,
77,
78,
79,
80,
81,
82,
83,
84,
85,
86,
87,
88,
89,
90,
91,
92,
95,
96,
97,
98,
99,
100,
101,
102,
104,
105,
106,
107,
108,
109,
113,
118,
119,
127,
128,
132,
137,
140,
159,
]

sn = [
377,
316,
275,
327,
321,
392,
360,
423,
385,
389,
399,
410,
414,
403,
366,
354,
370,
343,
320,
290,
305,
255,
254,
239,
282,
263,
222,
210,
181,
184,
162,
133,
148,
151,
146,
133,
95,
112,
102,
96,
79,
85,
74,
79,
72,
73,
60,
60,
50,
42,
47,
35,
44,
36,
23,
35,
30,
26,
32,
18,
20,
26,
14,
9,
20,
19,
17,
19,
12,
9,
12,
8,
10,
11,
7,
7,
3,
3,
6,
7,
4,
5,
4,
3,
5,
3,
5,
1,
4,
2,
2,
2,
5,
5,
2,
1,
1,
2,
4,
1,
1,
1,
1,
1,
2,
1,
1,
1,
1,
1,
1,
1,
1,
1,
1,
]

for index, nodeamount in enumerate(n):
    if sn[index] > 5:
        print("doing" +str(nodeamount))
        #get 100 tests
        maximum = 0.0
        minimum = 1.0
        ratioarray = []
        for test in range(99):
            base = [0, 1]
            edges = []
            randomorder = []
            totaledges = 2*nodeamount + 1
            for i in range(totaledges):
                edges.append(0)
                randomorder.append(i)
            ratios = []
            for i in range(sn[index]):
                random.shuffle(randomorder)
                for k in range(len(edges)):
                    edges[k] = 0
                triad = False
                done = False
                j = 0
                while done == False:
                    edge = randomorder[j]
                    j += 1
                    #odd edges correlate to connection with base[0] and even to base[1]
                    if edge == totaledges - 1:
                        done = True
                    elif (edge % 2) == 0:
                        edges[edge] = 1
                        if edges[edge + 1] == 1:
                            triad = True
                            done = True
                    else:
                        edges[edge] = 1
                        if edges[edge - 1] == 1:
                            triad = True
                            done = True
                if triad:
                    ratios.append(1.0)
                else:
                    ratios.append(0.0)
            avgratio = sum(ratios)/len(ratios)
            if avgratio > maximum:
                maximum = avgratio
            elif avgratio < minimum:
                minimum = avgratio
            ratioarray.append(avgratio)
        print(ratioarray)
        avgratio = sum(ratioarray)/len(ratioarray)
        stats = {"nodeamount":nodeamount,"sn":sn[index], "maximum":maximum,"minimum":minimum,"average":avgratio }
        try:
            with open(csv_file, 'a', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=csv_columns)
                writer.writerow(stats)
                csvfile.close()
        except IOError:
            print("I/O error")
        

