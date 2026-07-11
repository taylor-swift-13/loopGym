// Source: data/benchmarks/accelerating_invariant_generation/svcomp/sum04_true.c

#define a (2)
#define SIZE 8
void loopy_209(int i) { 
  int sn=0;
  {
  i=1;
  while (i<=SIZE) {
    sn = sn + a;
    i++;
  }
}
  {;
//@ assert(sn==SIZE*a || sn == 0);
}

}
