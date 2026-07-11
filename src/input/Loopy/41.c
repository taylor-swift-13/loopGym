// Source: data/benchmarks/LinearArbitrary-SeaHorn/invgen/split.c
extern int unknown(void);

extern int unknown();

void loopy_41(int j, int n) {
  int k = 100;
  int b = 0;
  int i;
  
  
  i = j = 0;
  {
  n = 0;
  while (n < 2*k) {
    if(b) {
          i++;
        } else {
          j++;
        }
        b = !b;
    n++;
  }
}
  {;
//@ assert(i == j);
}

}