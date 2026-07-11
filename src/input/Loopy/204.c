// Source: data/benchmarks/accelerating_invariant_generation/svcomp/count_up_down_true.c
extern unsigned int unknown_uint(void);

void loopy_204(unsigned int n)
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
