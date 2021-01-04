### Morphological analysis 
Preliminary dictionary for my morphological POS tagger.

There are too many morphological combination in hangul. 
So I begin with simple prefix-postfix separation

Some random results :

```
Term, TF, IDF, TF-IDF : 섹스하고     ..	0.00000	3.91	0.00000
Term, TF, IDF, TF-IDF : 섹스하ㄱ     ..	0.00000	3.22	0.00001
Term, TF, IDF, TF-IDF : 섹스학       ..	0.00000	3.22	0.00001
Term, TF, IDF, TF-IDF : 섹스하       ..	0.00001	2.12	0.00002
Term, TF, IDF, TF-IDF : 섹스ㅎ       ..	0.00002	1.83	0.00003  *
Term, TF, IDF, TF-IDF : 섹스         ..	0.00022	0.30	0.00007  ** -> 섹스 + 하고
Term, TF, IDF, TF-IDF : 섹ㅅ         ..	0.00037	-0.04	-0.00001
Term, TF, IDF, TF-IDF : 섹           ..	0.00194	-1.25	-0.00242
Term, TF, IDF, TF-IDF : 세           ..	0.01304	-3.50	-0.04569
Term, TF, IDF, TF-IDF : ㅅ           ..	0.45575	-6.32	-2.88234
Term, TF, IDF, TF-IDF : 재미있겠     ..	0.00000	3.91	0.00000
Term, TF, IDF, TF-IDF : 재미있게     ..	0.00001	3.22	0.00005
Term, TF, IDF, TF-IDF : 재미있ㄱ     ..	0.00004	2.12	0.00008
Term, TF, IDF, TF-IDF : 재미있       ..	0.00032	0.58	0.00019  *
Term, TF, IDF, TF-IDF : 재미이       ..	0.00042	0.51	0.00022  ** -> 재미이 + ㅆ겠
Term, TF, IDF, TF-IDF : 재미ㅇ       ..	0.00057	0.17	0.00010
Term, TF, IDF, TF-IDF : 재미         ..	0.00090	-0.54	-0.00049
Term, TF, IDF, TF-IDF : 재ㅁ         ..	0.00118	-0.77	-0.00091
Term, TF, IDF, TF-IDF : 재           ..	0.00597	-2.77	-0.01655
Term, TF, IDF, TF-IDF : ㅈ           ..	0.42036	-6.24	-2.62314
```

### Some results :

IDF가 음수가 되는게 문제 있어 보인다. 상수 N이 아니라 뭔가 적절한 특성이 필요함.

적당히 모델 만들고 test set 이용해서 tuning 및 verification 해야함.

```
tokenizer.tokenize("나는 자랑스러운 태극기 앞에 자유롭고 정의로운 대한민국의 무궁한 영광을 위하여 충성을 다할 것을 굳게 다짐합니다")
['나느', 'ㄴ', '자랑ㅅ', 'ㅡ러운', '태그', 'ㄱ기', '앞에', '자유로', 'ㅂ고', '정의', '로운', '대한', '민국의', '무구', 'ㅇ한', '영과', 'ㅇ을', '위하', '여', '충성', '을', '다하', 'ㄹ', '것을', '굳ㄱ', 'ㅔ', '다지', 'ㅁ합니다']
```
