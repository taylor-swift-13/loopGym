// Source: data/benchmarks/LinearArbitrary-SeaHorn/loops/loops/sum04_true-unreach-call_true-termination.i.annot.c

void loopy_74(int i){
  int sn=0;
  {
  i=1;
  while (i<=8) {
    sn = sn +(2);
    i++;
  }
}
  {;
//@ assert(sn==8*(2)|| sn == 0);
}

}