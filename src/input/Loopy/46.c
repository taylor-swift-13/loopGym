// Source: data/benchmarks/LinearArbitrary-SeaHorn/llreve/loop4_merged_safe.c
extern int unknown(void);

void loopy_46(int n) {
  
  int i1 = 0, i2 = 0;
  int j1 = 0, j2 = 0;

  while (1) {
    if (i1 < n + n) {
      j1++;
      i1++;
    }

    if (i2 < n) {
      j2 = j2 + 2;
      i2++;
    }
  }
  {;
//@ assert(j1==j2);
}

}