// Source: data/benchmarks/sv-benchmarks/loops/count_up_down-1.c
extern unsigned int unknown_uint(void);

void loopy_459(unsigned int n)
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
