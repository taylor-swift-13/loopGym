// Source: data/benchmarks/accelerating_invariant_generation/svcomp/for_infinite_loop_2_true.c
extern int unknown_int(void);

/*@
  requires n>0;
*/
void loopy_206(int n) {
  int i=0, x=0, y=0;
  
  
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
//@ assert(x!=0);
}

}
