// Source: data/benchmarks/LinearArbitrary-SeaHorn/loops/loop-new/count_by_1_true-unreach-call_true-termination.c
#define LARGE_INT 1000000

void loopy_63(int i) {
    
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