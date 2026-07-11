// Source: data/benchmarks/LinearArbitrary-SeaHorn/loops/loop-new/count_by_1_variant_true-unreach-call_true-termination.c
#define LARGE_INT 1000000

void loopy_64(int i) {
    
    {
  i = 0;
  while (i != LARGE_INT) {
    {;
    //@ assert(i <= LARGE_INT);
    }
    i++;
  }
}
    return;
}