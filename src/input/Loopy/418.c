// Source: data/benchmarks/sv-benchmarks/loop-zilu/benchmark32_linear.c
extern int unknown_int(void);
extern int unknown_bool(void);
/*@
  requires x==1 || x==2;
*/
void loopy_418(int x) {
  
  
  
  while (unknown_bool()) {
    if(x==1) x=2;
    else if (x==2) x=1;
  }
  {;
//@ assert(x<=8);
}

  return;
}