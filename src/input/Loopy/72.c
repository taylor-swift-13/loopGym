// Source: data/benchmarks/LinearArbitrary-SeaHorn/loops/loops/sum01_true-unreach-call_true-termination.i.annot.c
extern int unknown_int(void);

/*@
  requires n < 1000 && n >= -1000;
*/
void loopy_72(int i, int n){
  int sn=0;

  {
  i=1;
  while (i<=n) {
    sn = sn +(2);
    i++;
  }
}
  {;
//@ assert(sn==n*(2)|| sn == 0);
}

}