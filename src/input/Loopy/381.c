// Source: data/benchmarks/sv-benchmarks/loop-new/count_by_1.c
#define LARGE_INT 1000000

void loopy_381(int i) {
    
    {
  i = 0;
  while (i < LARGE_INT) {
    i++;
  }
}
    {;
//@ assert(i == LARGE_INT);
}

    return;
}