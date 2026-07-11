// Source: data/benchmarks/LinearArbitrary-SeaHorn/loops/loops/count_up_down_true-unreach-call_true-termination.i.annot.c
extern unsigned int unknown_uint(void);

void loopy_69(unsigned int n)
{
  
  unsigned int x=n, y=0;
  while(x>0)
  {
    x--;
    y++;
  }
  {;
//@ assert(y==n);
}

}