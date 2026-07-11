// Source: data/benchmarks/LinearArbitrary-SeaHorn/loops/loop-new/count_by_2_true-unreach-call_true-termination.c
#define LARGE_INT 1000000

void loopy_65(int i) {
    
    {
  i = 0;
  while (i < LARGE_INT) {
    i += 2;
  }
}
    {;
//@ assert(i == LARGE_INT);
}

    return;
}