// Source: data/benchmarks/LinearArbitrary-SeaHorn/pie/hola/32.c
extern int unknown(void);

extern int unknown();

void loopy_136(int j, int n) {
  int k = 100;
  int b = 0;
  int i = unknown();
  
  
  i = j = 0;
  {
  n = 0;
  while (n < 2*k) {
    if((int )b == 1) {
          i++;
          b = 0;
        } else if ((int )b == 0) {
          j++;
          b = 1;
        }
    n++;
  }
}
  {;
//@ assert(i == j);
}

}