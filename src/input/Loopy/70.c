// Source: data/benchmarks/LinearArbitrary-SeaHorn/loops/loops/for_infinite_loop_1_true-unreach-call_false-termination.i.annot.c
extern int unknown_int(void);

/*@
  requires n>0;
*/
void loopy_70(int n){
  unsigned int i=0;
  int x=0, y=0;
  

  {
  i=0;
  while (1) {
    {;
    //@ assert(x==0);
    }
    i++;
  }
}
  {;
//@ assert(x==0);
}

}